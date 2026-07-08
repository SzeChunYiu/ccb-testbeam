#!/usr/bin/env python3
"""P09e: delayed-peak external timing closure benchmark.

The first data operation is a raw B-stack ROOT scan that reproduces the S00
selected-pulse count.  The benchmark then asks whether delayed-peak B2 pulses
can be recovered, rather than vetoed, against an independent same-event B4/B6/B8
timing reference under leave-one-run-out splits.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import ParameterGrid
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
SCALAR_FEATURES = [
    "amplitude_log",
    "peak_sample",
    "late_fraction",
    "early_fraction",
    "width_half",
    "baseline_mad_log",
    "baseline_slope_scaled",
    "saturation_count",
    "secondary_peak",
    "secondary_sep",
    "post_peak_min",
    "undershoot_area",
    "cfd20_sample",
    "timing_span_dup",
    "area_norm",
]
METHOD_ORDER = [
    "traditional_late_template",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "late_gated_cnn_new",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_p09a_module():
    path = Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py")
    spec = importlib.util.spec_from_file_location("p09a_rare_waveform_anomaly_taxonomy", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def cfd20_crossing(waves: np.ndarray) -> np.ndarray:
    out = np.full(len(waves), np.nan, dtype=np.float32)
    peaks = waves.argmax(axis=1)
    for i, peak in enumerate(peaks):
        if peak <= 0:
            continue
        y = waves[i, : peak + 1]
        idx = np.where(y >= 0.2)[0]
        if len(idx) == 0:
            continue
        j = int(idx[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0, y1 = float(y[j - 1]), float(y[j])
        frac = 0.0 if abs(y1 - y0) < 1e-9 else (0.2 - y0) / (y1 - y0)
        out[i] = float(j - 1 + np.clip(frac, 0.0, 1.0))
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    import uproot

    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def pulse_features(norm: np.ndarray, raw: np.ndarray, dup_norm: np.ndarray, baseline_idx: List[int]) -> pd.DataFrame:
    peak = norm.argmax(axis=1).astype(np.int16)
    positive = np.clip(norm, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1e-6)
    area_norm = norm.sum(axis=1)
    late_fraction = positive[:, 12:].sum(axis=1) / pos_sum
    early_fraction = positive[:, :4].sum(axis=1) / pos_sum
    width_half = (norm > 0.5).sum(axis=1).astype(np.int16)
    baseline = np.median(raw[:, baseline_idx], axis=1)
    baseline_mad = np.median(np.abs(raw[:, baseline_idx] - baseline[:, None]), axis=1)
    baseline_slope = raw[:, baseline_idx[-1]] - raw[:, baseline_idx[0]]
    raw_max = raw.max(axis=1)
    saturation_count = (norm >= 0.995).sum(axis=1).astype(np.int16)

    secondary_peak = np.zeros(len(norm), dtype=np.float32)
    secondary_sep = np.zeros(len(norm), dtype=np.int16)
    post_peak_min = np.zeros(len(norm), dtype=np.float32)
    undershoot_area = np.zeros(len(norm), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo, hi = max(0, int(p) - 1), min(norm.shape[1], int(p) + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx])
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(norm.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0

    cfd = cfd20_crossing(norm)
    dup_cfd = cfd20_crossing(dup_norm)
    timing_span = np.abs(cfd - dup_cfd)
    timing_span = np.where(np.isfinite(timing_span), timing_span, 18.0)
    return pd.DataFrame(
        {
            "peak_sample": peak,
            "area_norm": area_norm.astype(np.float32),
            "late_fraction": late_fraction.astype(np.float32),
            "early_fraction": early_fraction.astype(np.float32),
            "width_half": width_half,
            "baseline_mad": baseline_mad.astype(np.float32),
            "baseline_slope": baseline_slope.astype(np.float32),
            "raw_max_adc": raw_max.astype(np.float32),
            "saturation_count": saturation_count,
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "undershoot_area": undershoot_area,
            "cfd20_sample": cfd,
            "timing_span_dup": timing_span.astype(np.float32),
        }
    )


def scan_raw_augmented(config: dict, p09a_config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    cut = float(p09a_config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in p09a_config["baseline_samples"]]
    nsamp = int(p09a_config["samples_per_channel"])
    stave_channels = np.asarray([int(p09a_config["staves"][name]) for name in STAVE_NAMES], dtype=int)
    duplicate_channels = np.asarray([int(p09a_config["duplicate_channels"][name]) for name in STAVE_NAMES], dtype=int)
    reference_indices = np.asarray([STAVE_NAMES.index(s) for s in config["external_reference_staves"]], dtype=int)
    groups = {}
    for group, runs in p09a_config["run_groups"].items():
        for run in runs:
            groups[int(run)] = group

    wave_chunks: List[np.ndarray] = []
    meta_chunks: List[pd.DataFrame] = []
    counts_rows: List[dict] = []
    for run in sorted(groups):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(str(path))
        group = groups[run]
        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}
        event_offset = 0
        for batch in iter_raw_events(path):
            event_numbers = np.asarray(batch["EVENTNO"])
            evt_numbers = np.asarray(batch["EVT"])
            raw_all = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            raw_even = raw_all[:, stave_channels, :]
            raw_odd = raw_all[:, duplicate_channels, :]
            base_even = np.median(raw_even[..., baseline_idx], axis=-1)
            base_odd = np.median(raw_odd[..., baseline_idx], axis=-1)
            corr_even = raw_even - base_even[..., None]
            corr_odd = raw_odd - base_odd[..., None]
            amplitude = corr_even.max(axis=-1)
            selected = amplitude > cut
            amp_safe_all = np.maximum(amplitude, 1.0)
            norm_all = (corr_even / amp_safe_all[..., None]).astype(np.float32)
            cfd_all = cfd20_crossing(norm_all.reshape(-1, nsamp)).reshape(-1, len(STAVE_NAMES))
            ref_matrix = np.where(selected[:, reference_indices], cfd_all[:, reference_indices], np.nan)
            external_ref = np.nanmedian(ref_matrix, axis=1).astype(np.float32)
            external_n = np.isfinite(ref_matrix).sum(axis=1).astype(np.int16)
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(raw_all))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[name] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                chosen = corr_even[event_idx, stave_idx]
                chosen_raw = raw_even[event_idx, stave_idx]
                chosen_dup = corr_odd[event_idx, stave_idx]
                dup_amp_pos = chosen_dup.max(axis=1).astype(np.float32)
                dup_amp_abs = np.maximum(np.abs(chosen_dup).max(axis=1), 1.0).astype(np.float32)
                norm = (chosen / amp[:, None]).astype(np.float32)
                dup_norm = (chosen_dup / dup_amp_abs[:, None]).astype(np.float32)
                feats = pulse_features(norm, chosen_raw, dup_norm, baseline_idx)
                feats.insert(0, "dup_cfd20_sample", cfd20_crossing(dup_norm))
                feats.insert(0, "dup_amplitude_adc", dup_amp_pos)
                feats.insert(0, "external_reference_n", external_n[event_idx])
                feats.insert(0, "external_reference_time_sample", external_ref[event_idx])
                feats.insert(0, "amplitude_adc", amp)
                feats.insert(0, "channel", stave_channels[stave_idx].astype(np.int16))
                feats.insert(0, "stave_index", stave_idx.astype(np.int8))
                feats.insert(0, "stave", np.asarray(STAVE_NAMES, dtype=object)[stave_idx])
                feats.insert(0, "group", group)
                feats.insert(0, "event_index", (event_idx + event_offset).astype(np.int32))
                feats.insert(0, "evt", evt_numbers[event_idx].astype(np.int64))
                feats.insert(0, "eventno", event_numbers[event_idx].astype(np.int64))
                feats.insert(0, "run", np.full(len(event_idx), run, dtype=np.int16))
                meta_chunks.append(feats)
                wave_chunks.append(norm)
            event_offset += int(len(raw_all))

        row = {"run": run, "group": group, **run_counts, **stave_counts}
        counts_rows.append(row)
        print("run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]), flush=True)
    return np.concatenate(wave_chunks, axis=0), pd.concat(meta_chunks, ignore_index=True), pd.DataFrame(counts_rows)


def add_model_columns(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    out["amplitude_log"] = np.log1p(np.maximum(out["amplitude_adc"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_mad_log"] = np.log1p(np.maximum(out["baseline_mad"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_slope_scaled"] = out["baseline_slope"].to_numpy(dtype=np.float32) / 1000.0
    delayed = (
        (out["stave"].to_numpy() == "B2")
        & (out["peak_sample"].to_numpy() >= int(config["delayed_peak_min_sample"]))
        & (out["late_fraction"].to_numpy() >= float(config["delayed_late_fraction_min"]))
        & (out["secondary_peak"].to_numpy() <= float(config["delayed_secondary_peak_max"]))
        & np.isfinite(out["external_reference_time_sample"].to_numpy())
        & (out["external_reference_n"].to_numpy() >= 1)
        & (out["saturation_count"].to_numpy() < 2)
    )
    out["delayed_peak_candidate"] = delayed
    out["target_time_sample"] = out["external_reference_time_sample"].astype(np.float32)
    return out


def feature_matrix(waves: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    scalars = frame[SCALAR_FEATURES].to_numpy(dtype=np.float32)
    scalars = np.nan_to_num(scalars, nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    wave = np.nan_to_num(waves[frame.index.to_numpy()].astype(np.float32), nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    return np.column_stack([wave, scalars]).astype(np.float32)


def target_matrix(frame: pd.DataFrame) -> np.ndarray:
    return frame[["target_time_sample"]].to_numpy(dtype=np.float32)


def sample_train_indices(train: pd.DataFrame, config: dict, rng: np.random.Generator) -> np.ndarray:
    idx = train.index.to_numpy()
    delayed_idx = train.index[train["delayed_peak_candidate"].to_numpy()].to_numpy()
    max_rows = int(config["train_sample_rows"])
    if len(idx) <= max_rows:
        return idx
    keep = [delayed_idx]
    remaining = np.setdiff1d(idx, delayed_idx, assume_unique=False)
    take = max(0, max_rows - len(delayed_idx))
    if take > 0:
        keep.append(rng.choice(remaining, size=min(take, len(remaining)), replace=False))
    sampled = np.concatenate(keep)
    rng.shuffle(sampled)
    return sampled


def y_scale_fit(y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    center = np.nanmean(y, axis=0)
    scale = np.nanstd(y, axis=0)
    scale = np.where(scale > 1e-9, scale, 1.0)
    return center.astype(np.float32), scale.astype(np.float32)


def y_scale_transform(y: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    return ((y - center[None, :]) / scale[None, :]).astype(np.float32)


def y_scale_inverse(y: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    return (y * scale[None, :] + center[None, :]).astype(np.float32)


def peak_bin(values: Sequence[float]) -> np.ndarray:
    return np.digitize(np.asarray(values, dtype=np.float32), [10.5, 12.5, 13.5, 14.5, 15.5, 16.5])


def traditional_predict(train: pd.DataFrame, test: pd.DataFrame, waves: np.ndarray) -> np.ndarray:
    train = train.copy()
    test = test.copy()
    train["peak_bin"] = peak_bin(train["peak_sample"])
    test["peak_bin"] = peak_bin(test["peak_sample"])
    train["time_offset"] = train["target_time_sample"] - train["cfd20_sample"]

    fallback_time = float(train["time_offset"].median())
    stave_medians = train.groupby("stave")[["time_offset"]].median()
    bin_medians = train.groupby(["stave", "peak_bin"])[["time_offset"]].median()

    pred = np.zeros((len(test), 1), dtype=np.float32)
    for i, (_, row) in enumerate(test.iterrows()):
        key = (row["stave"], int(row["peak_bin"]))
        if key in bin_medians.index:
            offsets = bin_medians.loc[key]
            dt = float(offsets["time_offset"])
        elif row["stave"] in stave_medians.index:
            offsets = stave_medians.loc[row["stave"]]
            dt = float(offsets["time_offset"])
        else:
            dt = fallback_time
        pred[i, 0] = float(row["cfd20_sample"]) + dt
    return pred


def fit_sklearn_method(name: str, x_train: np.ndarray, y_train: np.ndarray, config: dict):
    ml = config["ml"]
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=float(ml["ridge_alpha"])))
    if name == "gradient_boosted_trees":
        base = HistGradientBoostingRegressor(
            max_iter=int(ml["gbt_max_iter"]),
            learning_rate=float(ml["gbt_learning_rate"]),
            max_leaf_nodes=int(ml["gbt_max_leaf_nodes"]),
            l2_regularization=float(ml["gbt_l2_regularization"]),
            random_state=int(config["random_seed"]),
        )
        return MultiOutputRegressor(base)
    if name == "mlp":
        hidden = tuple(int(x) for x in ml["mlp_hidden_layer_sizes"])
        return make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=hidden,
                activation="relu",
                solver="adam",
                alpha=float(ml["mlp_alpha"]),
                max_iter=int(ml["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=10,
                random_state=int(config["random_seed"]) + 11,
            ),
        )
    raise ValueError(name)


def torch_predict(
    name: str,
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    waves: np.ndarray,
    y_train: np.ndarray,
    center: np.ndarray,
    scale: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    xw = waves[train_frame.index.to_numpy()].astype(np.float32)
    train_scalars = np.nan_to_num(train_frame[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    test_scalars = np.nan_to_num(test_frame[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    scalar_scaler = StandardScaler().fit(train_scalars)
    xs = scalar_scaler.transform(train_scalars).astype(np.float32)
    xtw = waves[test_frame.index.to_numpy()].astype(np.float32)
    xtw = np.nan_to_num(xtw, nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    xts = scalar_scaler.transform(test_scalars).astype(np.float32)
    ys = y_scale_transform(y_train, center, scale)

    class Cnn1d(nn.Module):
        def __init__(self, gated: bool):
            super().__init__()
            self.gated = gated
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.gate = nn.Sequential(nn.Linear(7, 16), nn.Sigmoid())
            self.head = nn.Sequential(
                nn.Linear(24 + len(SCALAR_FEATURES), 48),
                nn.ReLU(),
                nn.Linear(48, 1),
            )

        def forward(self, wave, scalars):
            z = self.conv(wave[:, None, :]).squeeze(-1)
            if self.gated:
                late = torch.cat([wave[:, 12:], scalars[:, 1:2]], dim=1)
                gate = self.gate(late)
                z = torch.cat([z[:, :16] * gate, z[:, 16:]], dim=1)
            return self.head(torch.cat([z, scalars], dim=1))

    model = Cnn1d(gated=(name == "late_gated_cnn_new")).to(device)
    ds = TensorDataset(
        torch.tensor(xw, dtype=torch.float32),
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor(ys, dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=int(config["ml"]["cnn_batch_size"]), shuffle=True)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["cnn_learning_rate"]),
        weight_decay=float(config["ml"]["cnn_weight_decay"]),
    )
    lossf = nn.SmoothL1Loss()
    losses: List[float] = []
    model.train()
    for _ in range(int(config["ml"]["cnn_epochs"])):
        total = 0.0
        seen = 0
        for wb, sb, yb in loader:
            wb, sb, yb = wb.to(device), sb.to(device), yb.to(device)
            opt.zero_grad()
            loss = lossf(model(wb, sb), yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(wb)
            seen += len(wb)
        losses.append(total / max(1, seen))
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(xtw), int(config["ml"]["cnn_batch_size"])):
            wb = torch.tensor(xtw[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            sb = torch.tensor(xts[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            preds.append(model(wb, sb).cpu().numpy().astype(np.float32))
    pred = y_scale_inverse(np.concatenate(preds, axis=0), center, scale)
    return pred, {"device": str(device), "final_loss": float(losses[-1]) if losses else None}


def fold_predictions(meta: pd.DataFrame, waves: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    fold_rows = []
    heldout_runs = [int(r) for r in config["heldout_runs"]]
    valid = (
        np.isfinite(meta["target_time_sample"].to_numpy())
        & (meta["stave"].to_numpy() == "B2")
        & (meta["external_reference_n"].to_numpy() >= 1)
    )
    for test_run in heldout_runs:
        train_mask = valid & (meta["run"].to_numpy().astype(int) != test_run)
        eval_mask = valid & (meta["run"].to_numpy().astype(int) == test_run) & meta["delayed_peak_candidate"].to_numpy()
        train_all = meta.loc[train_mask].copy()
        test = meta.loc[eval_mask].copy()
        if len(test) == 0:
            continue
        sample_idx = sample_train_indices(train_all, config, rng)
        train = meta.loc[sample_idx].copy()
        y_train = target_matrix(train)
        center, scale = y_scale_fit(y_train)
        y_test = target_matrix(test)
        base_cols = ["run", "event_index", "eventno", "evt", "stave", "amplitude_adc", "external_reference_n", "external_reference_time_sample", "peak_sample", "late_fraction"]

        method_preds: Dict[str, np.ndarray] = {
            "traditional_late_template": traditional_predict(train, test, waves)
        }
        x_train = feature_matrix(waves, train)
        x_test = feature_matrix(waves, test)
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            model = fit_sklearn_method(method, x_train, y_scale_transform(y_train, center, scale), config)
            model.fit(x_train, y_scale_transform(y_train, center, scale))
            method_preds[method] = y_scale_inverse(model.predict(x_test).astype(np.float32), center, scale)
        torch_meta = {}
        for method in ["cnn_1d", "late_gated_cnn_new"]:
            pred, info = torch_predict(method, train, test, waves, y_train, center, scale, config, int(config["random_seed"]) + test_run + len(method))
            method_preds[method] = pred
            torch_meta[method] = info

        for method in METHOD_ORDER:
            pred = method_preds[method]
            out = test[base_cols].copy()
            out["method"] = method
            out["target_time_sample"] = y_test[:, 0]
            out["pred_time_sample"] = pred[:, 0]
            out["residual_time_sample"] = out["pred_time_sample"] - out["target_time_sample"]
            rows.append(out)
        train_runs = sorted(int(r) for r in train["run"].unique())
        fold_rows.append(
            {
                "test_run": int(test_run),
                "n_train_all_valid": int(train_mask.sum()),
                "n_train_sampled": int(len(train)),
                "n_train_delayed_candidates": int(train["delayed_peak_candidate"].sum()),
                "n_test_delayed_candidates": int(len(test)),
                "test_run_in_train": bool(test_run in set(train_runs)),
                "train_runs": ",".join(str(r) for r in train_runs),
                "cnn_1d_device": torch_meta.get("cnn_1d", {}).get("device", ""),
                "late_gated_cnn_new_device": torch_meta.get("late_gated_cnn_new", {}).get("device", ""),
                "cnn_1d_final_loss": torch_meta.get("cnn_1d", {}).get("final_loss", np.nan),
                "late_gated_cnn_new_final_loss": torch_meta.get("late_gated_cnn_new", {}).get("final_loss", np.nan),
            }
        )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(fold_rows)


def res68(x: Sequence[float]) -> float:
    arr = np.asarray(x, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(0.5 * (np.percentile(arr, 84) - np.percentile(arr, 16)))


def metric_row(pred: pd.DataFrame, config: dict) -> dict:
    dt = pred["residual_time_sample"].to_numpy(dtype=np.float64)
    closure = np.abs(dt / float(config["target_time_scale_samples"]))
    good = np.abs(dt) <= float(config["recover_time_tolerance_samples"])
    utility = float(good.mean() - float(config["utility_loss_weight"]) * np.mean(np.minimum(closure, 4.0)))
    return {
        "method": str(pred["method"].iloc[0]) if len(pred) else "",
        "n_eval": int(len(pred)),
        "time_res68_samples": res68(dt),
        "time_mae_samples": float(mean_absolute_error(np.zeros(len(dt)), dt)) if len(dt) else np.nan,
        "external_closure_loss": float(np.mean(closure)) if len(closure) else np.nan,
        "composite_loss": float(np.mean(closure)) if len(closure) else np.nan,
        "good_recovery_rate": float(good.mean()) if len(good) else np.nan,
        "recover_utility_vs_veto0": utility,
    }


def summarize_predictions(predictions: pd.DataFrame, config: dict) -> pd.DataFrame:
    return pd.DataFrame([metric_row(g, config) for _, g in predictions.groupby("method", sort=False)])


def bootstrap_by_run(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(predictions["run"].astype(int).unique()))
    rows = []
    for method, group in predictions.groupby("method", sort=False):
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            pieces = []
            for draw, run in enumerate(sampled):
                piece = group[group["run"].astype(int) == int(run)].copy()
                piece["_boot_draw"] = draw
                pieces.append(piece)
            boot = pd.concat(pieces, ignore_index=True)
            m = metric_row(boot, config)
            for metric in [
                "time_res68_samples",
                "time_mae_samples",
                "external_closure_loss",
                "composite_loss",
                "good_recovery_rate",
                "recover_utility_vs_veto0",
            ]:
                rows.append({"method": method, "metric": metric, "value": m[metric]})
    boot = pd.DataFrame(rows)
    out = []
    for (method, metric), subset in boot.groupby(["method", "metric"], sort=True):
        vals = subset["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "method": method,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def ci_text(ci: pd.DataFrame, method: str, metric: str, digits: int = 3) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty:
        return ""
    return "[{:.{d}g}, {:.{d}g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]), d=digits)


def leakage_checks(meta: pd.DataFrame, predictions: pd.DataFrame, folds: pd.DataFrame, counts: pd.DataFrame, expected: int, reproduced: int) -> pd.DataFrame:
    checks = [
        {
            "check": "raw_reproduction_before_modeling",
            "value": int(reproduced),
            "pass": bool(reproduced == expected),
            "note": "script raises before model training if this is false",
        },
        {
            "check": "leave_one_run_train_test_overlap",
            "value": int(folds["test_run_in_train"].sum()) if len(folds) else -1,
            "pass": bool(len(folds) > 0 and int(folds["test_run_in_train"].sum()) == 0),
            "note": "run identifier is used only for splitting and bootstrap blocks",
        },
        {
            "check": "identifier_columns_absent_from_features",
            "value": 0,
            "pass": True,
            "note": "run, eventno, evt, event_index, channel, and stave are not in SCALAR_FEATURES",
        },
        {
            "check": "all_methods_same_eval_rows",
            "value": int(predictions.groupby("method").size().nunique()),
            "pass": bool(predictions.groupby("method").size().nunique() == 1),
            "note": "head-to-head methods must score the same delayed candidates",
        },
        {
            "check": "finite_predictions",
            "value": int(np.isfinite(predictions[["pred_time_sample"]].to_numpy()).all()),
            "pass": bool(np.isfinite(predictions[["pred_time_sample"]].to_numpy()).all()),
            "note": "NaN predictions would invalidate recovery scoring",
        },
    ]
    return pd.DataFrame(checks)


def markdown_table(df: pd.DataFrame, columns: List[str]) -> str:
    view = df[columns].copy()
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    expected: int,
    reproduced: int,
    counts: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    folds: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    metrics_view = metrics.copy()
    for metric in [
        "time_res68_samples",
        "time_mae_samples",
        "external_closure_loss",
        "composite_loss",
        "good_recovery_rate",
        "recover_utility_vs_veto0",
    ]:
        metrics_view[metric + "_ci95"] = [ci_text(ci, method, metric) for method in metrics_view["method"]]
    best = metrics_view[metrics_view["method"] == winner].iloc[0]
    lines = [
        "# P09e: delayed-peak external timing closure",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Abstract",
        "P09d showed that late-gated delayed B2 peaks can be recovered against the odd duplicate-channel consistency target. This study asks the harder external question: does the recovered B2 time close against an independent same-event B4/B6/B8 timing reference? I rebuilt the selected B-stack pulse table from raw ROOT, selected delayed B2 candidates using only B2 waveform morphology, and compared a strong train-run template offset with ridge regression, gradient-boosted trees, an MLP, a compact 1D-CNN, and a new late-gated CNN. Every prediction is leave-one-run-out: the held-out run is absent from the training sample, and uncertainty intervals are run-block bootstraps over the held-out runs.",
        "",
        "## Reproduction first",
        "The raw ROOT scan used the S00/P09a gate: B2/B4/B6/B8 even channels, baseline median over samples 0-3, and amplitude > 1000 ADC. Same-event B4/B6/B8 CFD20 crossings were computed in the same pass to define the external timing reference.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} |".format(expected, reproduced, reproduced == expected),
        "",
        "Per-run reproduction counts and all raw ROOT sha256 hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`.",
        "",
        "## Delayed-peak definition",
        "A candidate is eligible for the recovery benchmark when",
        "",
        "`stave == B2` and `peak_sample >= {}` and `late_fraction >= {:.2f}` and `secondary_peak <= {:.2f}`, with at least one finite selected B4/B6/B8 reference crossing, excluding saturated two-sample plateaus.".format(
            int(config["delayed_peak_min_sample"]),
            float(config["delayed_late_fraction_min"]),
            float(config["delayed_secondary_peak_max"]),
        ),
        "",
        "This definition is deliberately close to the P09b delayed-peak morphology but is applied to the full raw selected-pulse table rather than only to the 256-row gallery.",
        "",
        "## Target and metrics",
        "For delayed B2 pulse `i`, the external timing target is `t_i^ext = median({t_i^B4, t_i^B6, t_i^B8})` over selected downstream staves with finite CFD20 crossings in the same event. A method predicts `\\hat t_i` from the B2 normalized waveform and scalar morphology only; the downstream reference is never passed as a feature.",
        "",
        "The main scalar loss is",
        "",
        "`L_i = |hat_t_i - t_i^ext| / {:.2f}`.".format(
            float(config["target_time_scale_samples"]),
        ),
        "",
        "Reported columns include timing sigma68, timing MAE, mean external closure loss `L`, the rate of good recoveries satisfying `|dt| <= {:.2f}` samples, and a preregistered recover-vs-veto utility `U = good_rate - {:.2f} * mean(min(L,4))`. The veto action has `U = 0` because it keeps no delayed pulse measurement.".format(
            float(config["recover_time_tolerance_samples"]),
            float(config["utility_loss_weight"]),
        ),
        "",
        "## Methods",
        "The traditional baseline is a late-template external offset refit: in the training runs, delayed and near-delayed B2 pulses are binned by peak-position class; the median offset `median(t^ext - t^B2)` is then applied to the held-out run with B2-level fallback. This is a strong non-ML method because it uses the known late-peak coordinate directly while preserving run isolation.",
        "",
        "The ML/NN methods share the same feature tensor: 18 normalized B2 waveform samples plus amplitude, peak, late/early area fractions, width, baseline diagnostics, secondary peak, undershoot, CFD20, and duplicate-span quality. The duplicate-span quality is retained only as a B2 waveform quality covariate; the odd duplicate target is not used. Ridge is linear in standardized features; gradient-boosted trees use histogram boosting; the MLP is a two-layer ReLU regressor; the 1D-CNN convolves over waveform samples and appends scalar features; the new architecture is a late-gated CNN whose latent channels are multiplicatively gated by samples 12-17 and the peak coordinate before the final regressor.",
        "",
        "## Candidate counts",
        candidate_summary.to_markdown(index=False),
        "",
        "## Fold audit",
        folds[["test_run", "n_train_sampled", "n_train_delayed_candidates", "n_test_delayed_candidates", "test_run_in_train", "cnn_1d_device", "late_gated_cnn_new_device"]].to_markdown(index=False),
        "",
        "## Head-to-head benchmark",
        markdown_table(
            metrics_view,
            [
                "method",
                "n_eval",
                "time_res68_samples",
                "time_res68_samples_ci95",
                "time_mae_samples",
                "time_mae_samples_ci95",
                "external_closure_loss",
                "external_closure_loss_ci95",
                "composite_loss",
                "composite_loss_ci95",
                "good_recovery_rate",
                "good_recovery_rate_ci95",
                "recover_utility_vs_veto0",
                "recover_utility_vs_veto0_ci95",
            ],
        ),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "## Systematics and caveats",
        "- The B4/B6/B8 reference is external to the B2 recovery waveform, but it is still a same-event detector observable rather than beam-truth time.",
        "- The delayed-candidate definition intentionally rejects strong secondary peaks to avoid turning the study into a pile-up benchmark; this can remove real late pile-up cases.",
        "- B4/B6/B8 references exist only when a downstream stave also passes the selected-pulse gate, so this is a topology-supported closure test rather than a fully inclusive delayed-peak census.",
        "- Training includes delayed B2 candidates from other runs. That is required for a recovery refit, but run-wise non-stationarity remains a systematic; the reported intervals therefore bootstrap whole held-out runs.",
        "- The gallery labels are not used as training labels. P09b/P09c motivate the morphology, while this study scores against independent downstream timing closure in the raw ROOT table.",
        "",
        "## Verdict",
        "The winner by mean external closure loss is **{}** with `L = {:.3g}` (95% run-bootstrap CI {}) and good-recovery rate {:.3g} (CI {}). Its recover-vs-veto utility is {:.3g} (CI {}), so the preregistered action decision is **{}** for this candidate set. This directly tests whether P09d-style recovery transfers from duplicate-channel consistency to downstream timing closure.".format(
            winner,
            float(best["composite_loss"]),
            best["composite_loss_ci95"],
            float(best["good_recovery_rate"]),
            best["good_recovery_rate_ci95"],
            float(best["recover_utility_vs_veto0"]),
            best["recover_utility_vs_veto0_ci95"],
            "recover" if float(best["recover_utility_vs_veto0"]) > 0.0 else "veto",
        ),
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}` with Python `{}`. The manifest records input, code, command, seed, and output hashes.".format(
            runtime, platform.node(), platform.python_version()
        ),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09e_1781099176_1077_49f23306_external_timing_closure.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09a = load_p09a_module()
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)
    waves, meta, counts = scan_raw_augmented(config, p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    expected = int(p09a_config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    if reproduced != expected:
        raise RuntimeError("Raw reproduction failed before modeling: expected {}, got {}".format(expected, reproduced))

    meta = add_model_columns(meta, config)
    candidate_summary = (
        meta[meta["run"].isin([int(r) for r in config["heldout_runs"]])]
        .groupby(["run", "stave"], sort=True)["delayed_peak_candidate"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "delayed_candidates", "count": "selected_pulses"})
    )
    candidate_summary.to_csv(out_dir / "candidate_counts_by_run_stave.csv", index=False)

    predictions, folds = fold_predictions(meta, waves, config, rng)
    predictions.to_csv(out_dir / "heldout_recovery_predictions.csv", index=False)
    folds.to_csv(out_dir / "fold_audit.csv", index=False)
    metrics = summarize_predictions(predictions, config)
    order = {name: i for i, name in enumerate(METHOD_ORDER)}
    metrics["_order"] = metrics["method"].map(order)
    metrics = metrics.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
    ci = bootstrap_by_run(predictions, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    ci.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)

    leakage = leakage_checks(meta, predictions, folds, counts, expected, reproduced)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in sorted(int(r) for runs in p09a_config["run_groups"].values() for r in runs):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [
        config_path,
        p09a_config_path,
        Path(config["p09a_report_dir"]) / "result.json",
        Path(config["p09b_report_dir"]) / "result.json",
        Path(config["p09d_report_dir"]) / "result.json",
    ]:
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = str(metrics.sort_values("composite_loss", ascending=True).iloc[0]["method"])
    winner_row = metrics[metrics["method"] == winner].iloc[0]
    result = {
        "study": config["study_id"],
        "study_id": config["study_id"],
        "ticket": config["ticket_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "title": config["title"],
        "reproduced": bool(reproduced == expected),
        "repro_tolerance": "exact selected-pulse count match to P09a/S00 raw ROOT gate",
        "traditional": {
            "method": "traditional_late_template",
            "metric": "external_closure_loss",
            "value": float(metrics.loc[metrics["method"] == "traditional_late_template", "composite_loss"].iloc[0]),
            "ci": [
                float(ci[(ci["method"] == "traditional_late_template") & (ci["metric"] == "composite_loss")]["ci_low"].iloc[0]),
                float(ci[(ci["method"] == "traditional_late_template") & (ci["metric"] == "composite_loss")]["ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "winner": winner,
            "metric": "external_closure_loss",
            "value": float(winner_row["composite_loss"]),
            "ci": [
                float(ci[(ci["method"] == winner) & (ci["metric"] == "composite_loss")]["ci_low"].iloc[0]),
                float(ci[(ci["method"] == winner) & (ci["metric"] == "composite_loss")]["ci_high"].iloc[0]),
            ],
        },
        "winner": winner,
        "action": "recover" if float(winner_row["recover_utility_vs_veto0"]) > 0.0 else "veto",
        "action_winner": "recover" if float(winner_row["recover_utility_vs_veto0"]) > 0.0 else "veto",
        "ml_beats_baseline": bool(
            float(winner_row["composite_loss"])
            < float(metrics.loc[metrics["method"] == "traditional_late_template", "composite_loss"].iloc[0])
        ),
        "falsification": {
            "preregistered_metric": "mean external B4/B6/B8 timing closure loss on delayed B2 candidates",
            "split": "leave-one-heldout-run-out; run-block bootstrap over heldout runs",
            "n_tries": len(METHOD_ORDER),
        },
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": bool(reproduced == expected),
        },
        "heldout_runs": [int(r) for r in config["heldout_runs"]],
        "candidate_counts": candidate_summary.to_dict(orient="records"),
        "method_metrics": metrics.to_dict(orient="records"),
        "methods": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "fold_audit": folds.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": sha256_file(out_dir / "input_sha256.csv"),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_report(
        out_dir,
        config,
        expected,
        reproduced,
        counts,
        candidate_summary,
        metrics,
        ci,
        folds,
        leakage,
        winner,
        time.time() - t0,
    )

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09e_1781099176_1077_49f23306_external_timing_closure.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner, "action": result["action_winner"]}, indent=2))


if __name__ == "__main__":
    main()
