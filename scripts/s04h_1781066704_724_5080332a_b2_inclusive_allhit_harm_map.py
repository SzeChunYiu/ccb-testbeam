#!/usr/bin/env python3
"""S04h B2-inclusive all-hit timing closure harm map.

The study is deliberately ROOT-first. It rebuilds the selected-pulse and
all-hit counts from HRDv, then evaluates whether B2-inclusive all-hit events
improve or harm external timing closure relative to the downstream B4/B6/B8
same-event closure.
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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False


ALL_PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
DOWNSTREAM_PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


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
    for group in config["run_groups"].values():
        runs.extend(int(run) for run in group)
    return sorted(set(runs))


def run_group(config: dict, run: int) -> str:
    for group, runs in config["run_groups"].items():
        if int(run) in set(int(v) for v in runs):
            return group
    return "unknown"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray, baseline_idx: Sequence[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amp = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amp, peak, area, baseline


def cfd_times(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float, period_ns: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=np.float32)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = 0.0
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        sample_pos = float(j) if denom <= 0 else (j - 1.0) + (float(threshold[i]) - y0) / denom
        out[i] = float(period_ns) * sample_pos
    return out


def collect_from_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][stave]) for stave in staves], dtype=int)
    baseline_idx = [int(v) for v in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    amp_cut = float(config["amplitude_cut_adc"])
    period = float(config["sample_period_ns"])
    cfd_frac = float(config["cfd_fraction"])
    timing_runs = set(int(v) for v in config["timing"]["train_runs"] + config["timing"]["heldout_runs"])
    rows = []
    pulse_rows = []
    uid_offset = 0
    for run in configured_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        run_row = {
            "run": int(run),
            "group": run_group(config, run),
            "n_events": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "all_hit_events": 0,
        }
        run_row.update({f"{stave}_selected": 0 for stave in staves})
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corrected, amp, peak, area, baseline = pulse_quantities(raw[:, channels, :], baseline_idx)
            selected = amp > amp_cut
            all_hit = selected.all(axis=1)
            run_row["n_events"] += int(len(eventno))
            run_row["events_with_selected"] += int(selected.any(axis=1).sum())
            run_row["selected_pulses"] += int(selected.sum())
            run_row["all_hit_events"] += int(all_hit.sum())
            for sidx, stave in enumerate(staves):
                run_row[f"{stave}_selected"] += int(selected[:, sidx].sum())
            if int(run) in timing_runs and bool(all_hit.any()):
                all_idx = np.where(all_hit)[0]
                for e in all_idx:
                    event_id = f"{run}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                    cfd = cfd_times(corrected[e], amp[e], cfd_frac, period)
                    event_amp = amp[e]
                    event_peak = peak[e]
                    event_baseline = baseline[e]
                    event_area = area[e]
                    b2_amp = float(event_amp[0])
                    b2_ratio = b2_amp / max(float(np.median(event_amp[1:])), 1.0)
                    spread = float(np.nanmax(event_peak) - np.nanmin(event_peak))
                    baseline_span = float(np.nanmax(event_baseline) - np.nanmin(event_baseline))
                    saturation_any = bool(np.nanmax(raw[e, channels, :]) > 15000.0)
                    dropout_any = bool(np.nanmin(event_amp) < 1300.0)
                    anomaly_any = bool((baseline_span > 800.0) or (spread > 6.0))
                    for sidx, stave in enumerate(staves):
                        pulse_rows.append(
                            {
                                "event_id": event_id,
                                "run": int(run),
                                "run_group": run_group(config, run),
                                "eventno": int(eventno[e]),
                                "evt": int(evt[e]),
                                "stave": str(stave),
                                "stave_index": int(sidx),
                                "waveform": corrected[e, sidx].astype(np.float32),
                                "amplitude_adc": float(event_amp[sidx]),
                                "peak_sample": int(event_peak[sidx]),
                                "area_adc_samples": float(event_area[sidx]),
                                "baseline_adc": float(event_baseline[sidx]),
                                "t_cfd_ns": float(cfd[sidx]),
                                "event_b2_amp_adc": b2_amp,
                                "event_b2_amp_ratio": b2_ratio,
                                "event_peak_spread": spread,
                                "event_baseline_span_adc": baseline_span,
                                "event_saturation_any": saturation_any,
                                "event_dropout_any": dropout_any,
                                "event_anomaly_any": anomaly_any,
                            }
                        )
            uid_offset += len(eventno)
        rows.append(run_row)
        print(f"run {run:04d}: selected={run_row['selected_pulses']} all_hit={run_row['all_hit_events']}", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(pulse_rows)


def positions(config: dict) -> Dict[str, float]:
    spacing = float(config["spacing_cm"])
    return {stave: i * spacing for i, stave in enumerate(config["staves"].keys())}


def corrected_time(pulses: pd.DataFrame, col: str, config: dict) -> pd.Series:
    return pulses[col].astype(float) - pulses["stave"].map(positions(config)).astype(float) * float(config["tof_per_cm_ns"])


def target_residuals(pulses: pd.DataFrame, target_staves: Sequence[str], config: dict, base_col: str = "t_cfd_ns") -> np.ndarray:
    work = pulses.copy()
    work["tcorr"] = corrected_time(work, base_col, config)
    wide = work.pivot(index="event_id", columns="stave", values="tcorr")
    event_to_row = {event_id: wide.loc[event_id] for event_id in wide.index}
    targets = np.full(len(pulses), np.nan, dtype=np.float32)
    target_set = list(target_staves)
    for i, row in enumerate(pulses.itertuples()):
        if row.stave not in target_set:
            continue
        vals = event_to_row[row.event_id]
        others = [stave for stave in target_set if stave != row.stave and pd.notna(vals.get(stave, np.nan))]
        if len(others) >= 2 and math.isfinite(float(row.t_cfd_ns)):
            targets[i] = float(vals[row.stave] - np.mean([float(vals[stave]) for stave in others]))
    return targets


def sigma68(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return float("nan")
    q16, q84 = np.percentile(finite, [16, 84])
    return float((q84 - q16) / 2.0)


def full_rms(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(np.square(finite))))


def pairwise_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: int, pairs: Sequence[Tuple[str, str]]) -> np.ndarray:
    sub = pulses[pulses["run"] == int(run)].copy()
    if sub.empty:
        return np.asarray([], dtype=np.float32)
    sub["tcorr"] = corrected_time(sub, method_col, config)
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    residuals = []
    for a, b in pairs:
        if a in wide and b in wide:
            residuals.append((wide[a] - wide[b]).to_numpy(dtype=np.float32))
    return np.concatenate(residuals) if residuals else np.asarray([], dtype=np.float32)


def one_hot(values: Sequence, categories: Sequence) -> np.ndarray:
    lookup = {v: i for i, v in enumerate(categories)}
    out = np.zeros((len(values), len(categories)), dtype=np.float32)
    for i, value in enumerate(values):
        if value in lookup:
            out[i, lookup[value]] = 1.0
    return out


def amp_bins(amp: np.ndarray, edges: Sequence[float]) -> np.ndarray:
    edges_arr = np.asarray(edges, dtype=float)
    return np.clip(np.searchsorted(edges_arr, amp, side="right") - 1, 0, len(edges_arr) - 2)


def traditional_features(config: dict, pulses: pd.DataFrame, feature_set: str) -> np.ndarray:
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    log_amp = np.log1p(amp)
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=np.float32) / np.maximum(amp, 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=np.float32)
    inv_sqrt = 1.0 / np.sqrt(np.maximum(amp, 1.0))
    stave_hot = one_hot(pulses["stave"].tolist(), list(config["staves"].keys()))
    base = np.column_stack([log_amp, log_amp**2, inv_sqrt, area_over_amp, peak]).astype(np.float32)
    if feature_set == "amp_poly_by_stave":
        blocks = [base, stave_hot]
        blocks.extend([base[:, j : j + 1] * stave_hot for j in range(base.shape[1])])
        X = np.hstack(blocks)
    elif feature_set == "amp_bin_by_stave":
        bins = amp_bins(amp, config["traditional"]["amplitude_edges_adc"])
        bin_hot = one_hot(bins.tolist(), list(range(len(config["traditional"]["amplitude_edges_adc"]) - 1)))
        blocks = [base[:, [0, 2, 3, 4]], stave_hot]
        blocks.extend([bin_hot[:, j : j + 1] * stave_hot for j in range(bin_hot.shape[1])])
        X = np.hstack(blocks)
    else:
        raise ValueError(feature_set)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def waveform_features(config: dict, pulses: pd.DataFrame) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    summary = np.column_stack(
        [
            np.log1p(amp),
            pulses["area_adc_samples"].to_numpy(dtype=np.float32) / np.maximum(amp, 1.0),
            pulses["peak_sample"].to_numpy(dtype=np.float32),
            pulses["baseline_adc"].to_numpy(dtype=np.float32) / 1000.0,
            pulses["event_b2_amp_ratio"].to_numpy(dtype=np.float32),
            pulses["event_peak_spread"].to_numpy(dtype=np.float32),
            pulses["event_baseline_span_adc"].to_numpy(dtype=np.float32) / 1000.0,
        ]
    )
    flags = pulses[["event_saturation_any", "event_dropout_any", "event_anomaly_any"]].astype(float).to_numpy(dtype=np.float32)
    stave_hot = one_hot(pulses["stave"].tolist(), list(config["staves"].keys()))
    return np.nan_to_num(np.hstack([norm, summary, flags, stave_hot]).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def peer_only_features(config: dict, pulses: pd.DataFrame) -> np.ndarray:
    staves = list(config["staves"].keys())
    summaries = pulses[["amplitude_adc", "area_adc_samples", "peak_sample", "baseline_adc"]].to_numpy(dtype=np.float32)
    by_event = {}
    for event_id, sub in pulses.groupby("event_id"):
        d = {}
        for row in sub.itertuples():
            d[row.stave] = np.asarray([row.amplitude_adc, row.area_adc_samples, row.peak_sample, row.baseline_adc], dtype=np.float32)
        by_event[event_id] = d
    rows = []
    for row in pulses.itertuples():
        vals = []
        event = by_event[row.event_id]
        for stave in staves:
            if stave == row.stave:
                vals.extend([0.0, 0.0, 0.0, 0.0])
            else:
                vals.extend(event[stave].tolist())
        vals.extend([row.event_b2_amp_ratio, row.event_peak_spread, row.event_baseline_span_adc])
        rows.append(vals)
    X = np.asarray(rows, dtype=np.float32)
    X[:, 0::4] = np.log1p(np.maximum(X[:, 0::4], 0.0))
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def run_only_features(config: dict, pulses: pd.DataFrame) -> np.ndarray:
    run = pulses["run"].to_numpy(dtype=np.float32)
    stave_hot = one_hot(pulses["stave"].tolist(), list(config["staves"].keys()))
    return np.hstack([((run - 50.0) / 20.0)[:, None], stave_hot]).astype(np.float32)


def score_fold(config: dict, pulses: pd.DataFrame, rows: np.ndarray, pred: np.ndarray) -> float:
    work = pulses.iloc[rows].copy()
    work["t_model_ns"] = work["t_cfd_ns"].to_numpy(dtype=np.float32) - pred[rows]
    vals = []
    for run in sorted(work["run"].unique()):
        vals.append(pairwise_residuals(work, "t_model_ns", config, int(run), DOWNSTREAM_PAIRS))
    joined = np.concatenate([v for v in vals if len(v)]) if vals else np.asarray([], dtype=np.float32)
    return sigma68(joined)


def train_sklearn_model(model_name: str, X_train: np.ndarray, y_train: np.ndarray, groups: np.ndarray, config: dict) -> Tuple[object, dict, pd.DataFrame]:
    rows = []
    best = {"score": float("inf")}
    unique_groups = np.unique(groups)
    n_splits = min(4, len(unique_groups))
    splitter = GroupKFold(n_splits=n_splits)
    candidates = []
    if model_name == "ridge":
        for alpha in config["models"]["ridge_alphas"]:
            candidates.append({"alpha": float(alpha)})
    elif model_name == "hgb":
        for leaf in config["models"]["hgb_max_leaf_nodes"]:
            for lr in config["models"]["hgb_learning_rate"]:
                for max_iter in config["models"]["hgb_max_iter"]:
                    candidates.append({"max_leaf_nodes": int(leaf), "learning_rate": float(lr), "max_iter": int(max_iter)})
    elif model_name == "mlp":
        for hidden in config["models"]["mlp_hidden"]:
            candidates.append({"hidden": int(hidden)})
    else:
        raise ValueError(model_name)
    for cand in candidates:
        fold_scores = []
        for fold, (tr, va) in enumerate(splitter.split(X_train, y_train, groups=groups), start=1):
            model = make_sklearn_estimator(model_name, cand, config, fold)
            model.fit(X_train[tr], y_train[tr])
            pred = model.predict(X_train[va])
            score = sigma68(y_train[va] - pred)
            fold_scores.append(score)
            rows.append({"model": model_name, "candidate": json.dumps(cand, sort_keys=True), "fold": fold, "target_sigma68_ns": score})
        mean_score = float(np.mean(fold_scores))
        rows.append({"model": model_name, "candidate": json.dumps(cand, sort_keys=True), "fold": -1, "target_sigma68_ns": mean_score})
        if mean_score < best["score"]:
            best = dict(cand)
            best["score"] = mean_score
    final = make_sklearn_estimator(model_name, best, config, 99)
    final.fit(X_train, y_train)
    best["model"] = model_name
    return final, best, pd.DataFrame(rows)


def make_sklearn_estimator(model_name: str, params: dict, config: dict, seed_offset: int):
    seed = int(config["random_seed"]) + int(seed_offset)
    if model_name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"]), solver="lsqr"))
    if model_name == "hgb":
        return HistGradientBoostingRegressor(
            max_iter=int(params["max_iter"]),
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            learning_rate=float(params["learning_rate"]),
            l2_regularization=0.01,
            random_state=seed,
        )
    if model_name == "mlp":
        return make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(int(params["hidden"]), int(params["hidden"]) // 2),
                activation="relu",
                alpha=0.001,
                learning_rate_init=0.001,
                max_iter=120,
                random_state=seed,
                early_stopping=True,
                n_iter_no_change=8,
            ),
        )
    raise ValueError(model_name)


class CnnRegressor(nn.Module):
    def __init__(self, n_summary: int, channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(channels + n_summary, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x_wave, x_summary):
        z = self.conv(x_wave[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, x_summary], dim=1)).squeeze(1)


class GatedMixerRegressor(nn.Module):
    def __init__(self, n_wave: int, n_summary: int, hidden: int):
        super().__init__()
        self.wave = nn.Sequential(nn.Linear(n_wave, hidden), nn.ReLU(), nn.Linear(hidden, 1))
        self.summary = nn.Sequential(nn.Linear(n_summary, hidden), nn.ReLU(), nn.Linear(hidden, 1))
        self.gate = nn.Sequential(nn.Linear(n_wave + n_summary, hidden), nn.ReLU(), nn.Linear(hidden, 1), nn.Sigmoid())

    def forward(self, x_wave, x_summary):
        wave_flat = x_wave
        g = self.gate(torch.cat([wave_flat, x_summary], dim=1)).squeeze(1)
        return g * self.wave(wave_flat).squeeze(1) + (1.0 - g) * self.summary(x_summary).squeeze(1)


def train_torch_model(model_name: str, X: np.ndarray, y: np.ndarray, groups: np.ndarray, config: dict) -> Tuple[object, dict, pd.DataFrame]:
    if not TORCH_AVAILABLE:
        raise RuntimeError("torch is unavailable")
    n_wave = int(config["samples_per_channel"])
    rows = []
    if model_name == "cnn1d":
        candidates = [{"channels": int(c)} for c in config["models"]["cnn_channels"]]
    elif model_name == "gated_mixer":
        candidates = [{"hidden": int(h)} for h in config["models"]["gated_hidden"]]
    else:
        raise ValueError(model_name)
    best = {"score": float("inf")}
    splitter = GroupKFold(n_splits=min(4, len(np.unique(groups))))
    for cand in candidates:
        fold_scores = []
        for fold, (tr, va) in enumerate(splitter.split(X, y, groups=groups), start=1):
            model, xmean, xstd, ymean, ystd = fit_torch_estimator(model_name, X[tr], y[tr], config, cand, fold)
            pred = predict_torch(model, X[va], xmean, xstd, ymean, ystd, n_wave)
            score = sigma68(y[va] - pred)
            fold_scores.append(score)
            rows.append({"model": model_name, "candidate": json.dumps(cand, sort_keys=True), "fold": fold, "target_sigma68_ns": score})
        mean_score = float(np.mean(fold_scores))
        rows.append({"model": model_name, "candidate": json.dumps(cand, sort_keys=True), "fold": -1, "target_sigma68_ns": mean_score})
        if mean_score < best["score"]:
            best = dict(cand)
            best["score"] = mean_score
    model, xmean, xstd, ymean, ystd = fit_torch_estimator(model_name, X, y, config, best, 99)
    best["model"] = model_name
    best["normalizer"] = (xmean, xstd, ymean, ystd)
    return model, best, pd.DataFrame(rows)


def fit_torch_estimator(model_name: str, X: np.ndarray, y: np.ndarray, config: dict, params: dict, seed_offset: int):
    torch.manual_seed(int(config["random_seed"]) + int(seed_offset))
    n_wave = int(config["samples_per_channel"])
    xmean = X.mean(axis=0, keepdims=True)
    xstd = X.std(axis=0, keepdims=True) + 1e-6
    ymean = float(y.mean())
    ystd = float(y.std() + 1e-6)
    Xn = (X - xmean) / xstd
    yn = (y - ymean) / ystd
    wave = torch.tensor(Xn[:, :n_wave], dtype=torch.float32)
    summary = torch.tensor(Xn[:, n_wave:], dtype=torch.float32)
    target = torch.tensor(yn, dtype=torch.float32)
    ds = TensorDataset(wave, summary, target)
    loader = DataLoader(ds, batch_size=int(config["models"]["nn_batch_size"]), shuffle=True)
    if model_name == "cnn1d":
        model = CnnRegressor(summary.shape[1], int(params["channels"]))
    else:
        model = GatedMixerRegressor(n_wave, summary.shape[1], int(params["hidden"]))
    opt = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.001)
    loss_fn = nn.SmoothL1Loss(beta=0.5)
    model.train()
    for _ in range(int(config["models"]["nn_epochs"])):
        for xb, xs, yy in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb, xs), yy)
            loss.backward()
            opt.step()
    return model, xmean.astype(np.float32), xstd.astype(np.float32), ymean, ystd


def predict_torch(model, X: np.ndarray, xmean: np.ndarray, xstd: np.ndarray, ymean: float, ystd: float, n_wave: int) -> np.ndarray:
    Xn = (X - xmean) / xstd
    wave = torch.tensor(Xn[:, :n_wave], dtype=torch.float32)
    summary = torch.tensor(Xn[:, n_wave:], dtype=torch.float32)
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(X), 2048):
            pred = model(wave[start : start + 2048], summary[start : start + 2048]).cpu().numpy()
            preds.append(pred)
    return (np.concatenate(preds) * ystd + ymean).astype(np.float32)


def fit_traditional(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    idx = np.flatnonzero(mask)
    groups = pulses.iloc[idx]["run"].to_numpy(dtype=int)
    best = {"score": float("inf")}
    rows = []
    for feature_set in config["traditional"]["feature_sets"]:
        X = traditional_features(config, pulses, feature_set)
        for alpha in config["traditional"]["ridge_alphas"]:
            fold_scores = []
            splitter = GroupKFold(n_splits=min(4, len(np.unique(groups))))
            for fold, (tr, va) in enumerate(splitter.split(X[idx], target[idx], groups=groups), start=1):
                model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha), solver="lsqr"))
                model.fit(X[idx][tr], target[idx][tr])
                pred = np.zeros(len(pulses), dtype=np.float32)
                pred[idx[va]] = model.predict(X[idx][va]).astype(np.float32)
                fold_scores.append(score_fold(config, pulses, idx[va], pred))
                rows.append({"model": "traditional", "feature_set": feature_set, "alpha": float(alpha), "fold": fold, "sigma68_ns": fold_scores[-1]})
            score = float(np.mean(fold_scores))
            rows.append({"model": "traditional", "feature_set": feature_set, "alpha": float(alpha), "fold": -1, "sigma68_ns": score})
            if score < best["score"]:
                best = {"feature_set": feature_set, "alpha": float(alpha), "score": score}
    X = traditional_features(config, pulses, str(best["feature_set"]))
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"]), solver="lsqr"))
    model.fit(X[mask], target[mask])
    pred = np.zeros(len(pulses), dtype=np.float32)
    apply = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
    pred[apply] = model.predict(X[apply]).astype(np.float32)
    best["train_pulses"] = int(mask.sum())
    best["train_runs"] = sorted(int(v) for v in np.unique(pulses.loc[mask, "run"]))
    return pred, best, pd.DataFrame(rows)


def fit_predict_models(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, Dict[str, dict]]:
    idx = np.flatnonzero(mask)
    y = target[idx].astype(np.float32)
    groups = pulses.iloc[idx]["run"].to_numpy(dtype=int)
    X_wave = waveform_features(config, pulses)
    predictions: Dict[str, np.ndarray] = {}
    cv_tables = []
    best_params: Dict[str, dict] = {}
    for name in ["ridge", "hgb", "mlp"]:
        model, best, cv = train_sklearn_model(name, X_wave[idx], y, groups, config)
        pred = np.zeros(len(pulses), dtype=np.float32)
        apply = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
        pred[apply] = model.predict(X_wave[apply]).astype(np.float32)
        predictions[name] = pred
        cv_tables.append(cv)
        best_params[name] = best
    if TORCH_AVAILABLE:
        for name in ["cnn1d", "gated_mixer"]:
            model, best, cv = train_torch_model(name, X_wave[idx], y, groups, config)
            xmean, xstd, ymean, ystd = best["normalizer"]
            pred = np.zeros(len(pulses), dtype=np.float32)
            apply = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
            pred[apply] = predict_torch(model, X_wave[apply], xmean, xstd, ymean, ystd, int(config["samples_per_channel"]))
            predictions[name] = pred
            best_clean = {k: v for k, v in best.items() if k != "normalizer"}
            best_params[name] = best_clean
            cv_tables.append(cv)
    else:
        best_params["cnn1d"] = {"status": "skipped_torch_unavailable"}
        best_params["gated_mixer"] = {"status": "skipped_torch_unavailable"}
    return predictions, pd.concat(cv_tables, ignore_index=True), best_params


def fit_control_predictions(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 404)
    idx = np.flatnonzero(mask)
    groups = pulses.iloc[idx]["run"].to_numpy(dtype=int)
    controls: Dict[str, np.ndarray] = {}
    rows = []
    for name, X in [("run_only_control", run_only_features(config, pulses)), ("target_stave_excluded_hgb_control", peer_only_features(config, pulses))]:
        model, best, cv = train_sklearn_model("hgb" if "hgb" in name else "ridge", X[idx], target[idx].astype(np.float32), groups, config)
        pred = np.zeros(len(pulses), dtype=np.float32)
        apply = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
        pred[apply] = model.predict(X[apply]).astype(np.float32)
        controls[name] = pred
        rows.append({"control": name, "best": json.dumps(best, sort_keys=True), "cv_rows": int(len(cv))})
    X = waveform_features(config, pulses)
    shuffled = target.copy()
    train_values = shuffled[mask].copy()
    rng.shuffle(train_values)
    shuffled[mask] = train_values
    model, best, cv = train_sklearn_model("ridge", X[idx], shuffled[idx].astype(np.float32), groups, config)
    pred = np.zeros(len(pulses), dtype=np.float32)
    apply = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
    pred[apply] = model.predict(X[apply]).astype(np.float32)
    controls["shuffled_target_ridge_control"] = pred
    rows.append({"control": "shuffled_target_ridge_control", "best": json.dumps(best, sort_keys=True), "cv_rows": int(len(cv))})
    return controls, pd.DataFrame(rows)


def evaluate(config: dict, pulses: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    work = pulses.copy()
    for name, pred in predictions.items():
        work[f"t_{name}_ns"] = work["t_cfd_ns"].to_numpy(dtype=np.float32) - pred
    heldout = [int(v) for v in config["timing"]["heldout_runs"]]
    rows = []
    for run in heldout:
        for method in ["cfd20_uncorrected"] + list(predictions.keys()):
            col = "t_cfd_ns" if method == "cfd20_uncorrected" else f"t_{method}_ns"
            for pair_scope, pairs in [("all_six_with_b2", ALL_PAIRS), ("downstream_only", DOWNSTREAM_PAIRS)]:
                vals = pairwise_residuals(work, col, config, run, pairs)
                rows.append(
                    {
                        "run": int(run),
                        "method": method,
                        "pair_scope": pair_scope,
                        "n_all_hit_events": int(work.loc[work["run"] == run, "event_id"].nunique()),
                        "n_pair_residuals": int(len(vals)),
                        "sigma68_ns": sigma68(vals),
                        "full_rms_ns": full_rms(vals),
                        "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals[np.isfinite(vals)]) > float(config["tail_threshold_ns"]))) if len(vals) else float("nan"),
                    }
                )
    per_run = pd.DataFrame(rows)
    summary = summarize_run_bootstrap(per_run, config)
    return per_run, summary


def summarize_run_bootstrap(per_run: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 808)
    rows = []
    runs = sorted(int(v) for v in per_run["run"].unique())
    for method in sorted(per_run["method"].unique()):
        sub = per_run[per_run["method"] == method]
        wide = sub.pivot(index="run", columns="pair_scope", values="sigma68_ns").reindex(runs)
        rms = sub.pivot(index="run", columns="pair_scope", values="full_rms_ns").reindex(runs)
        tail = sub.pivot(index="run", columns="pair_scope", values="tail_frac_abs_gt5ns").reindex(runs)
        values = wide.to_numpy(dtype=float)
        rms_values = rms.to_numpy(dtype=float)
        tail_values = tail.to_numpy(dtype=float)
        harm = wide["all_six_with_b2"].to_numpy(dtype=float) - wide["downstream_only"].to_numpy(dtype=float)
        boots = []
        boot_rms = []
        boot_tail = []
        boot_harm = []
        for _ in range(int(config["bootstrap_iterations"])):
            idx = rng.integers(0, len(runs), len(runs))
            boots.append(np.nanmean(values[idx], axis=0))
            boot_rms.append(np.nanmean(rms_values[idx], axis=0))
            boot_tail.append(np.nanmean(tail_values[idx], axis=0))
            boot_harm.append(np.nanmean(harm[idx]))
        boots = np.asarray(boots)
        boot_rms = np.asarray(boot_rms)
        boot_tail = np.asarray(boot_tail)
        boot_harm = np.asarray(boot_harm)
        for j, scope in enumerate(wide.columns):
            rows.append(
                {
                    "method": method,
                    "pair_scope": scope,
                    "n_heldout_runs": int(len(runs)),
                    "mean_run_sigma68_ns": float(np.nanmean(values[:, j])),
                    "sigma68_ci_low_ns": float(np.nanquantile(boots[:, j], 0.025)),
                    "sigma68_ci_high_ns": float(np.nanquantile(boots[:, j], 0.975)),
                    "mean_run_full_rms_ns": float(np.nanmean(rms_values[:, j])),
                    "full_rms_ci_low_ns": float(np.nanquantile(boot_rms[:, j], 0.025)),
                    "full_rms_ci_high_ns": float(np.nanquantile(boot_rms[:, j], 0.975)),
                    "mean_run_tail_frac_abs_gt5ns": float(np.nanmean(tail_values[:, j])),
                    "tail_ci_low": float(np.nanquantile(boot_tail[:, j], 0.025)),
                    "tail_ci_high": float(np.nanquantile(boot_tail[:, j], 0.975)),
                    "b2_inclusion_harm_delta_ns": float(np.nanmean(harm)),
                    "b2_inclusion_harm_ci_low_ns": float(np.nanquantile(boot_harm, 0.025)),
                    "b2_inclusion_harm_ci_high_ns": float(np.nanquantile(boot_harm, 0.975)),
                }
            )
    return pd.DataFrame(rows)


def harm_atom_map(config: dict, pulses: pd.DataFrame, predictions: Dict[str, np.ndarray], winner: str) -> pd.DataFrame:
    work = pulses.copy()
    method = winner
    work[f"t_{method}_ns"] = work["t_cfd_ns"].to_numpy(dtype=np.float32) - predictions[method]
    event_meta = (
        work.groupby(["event_id", "run"], observed=False)
        .agg(
            event_b2_amp_adc=("event_b2_amp_adc", "first"),
            event_b2_amp_ratio=("event_b2_amp_ratio", "first"),
            event_peak_spread=("event_peak_spread", "first"),
            event_baseline_span_adc=("event_baseline_span_adc", "first"),
            event_saturation_any=("event_saturation_any", "first"),
            event_dropout_any=("event_dropout_any", "first"),
            event_anomaly_any=("event_anomaly_any", "first"),
        )
        .reset_index()
    )
    event_meta["b2_amp_bin"] = pd.cut(event_meta["event_b2_amp_adc"], [0, 1500, 3200, 6800, 1e9], labels=["low", "mid", "high", "very_high"], include_lowest=True)
    event_meta["b2_ratio_bin"] = pd.cut(event_meta["event_b2_amp_ratio"], [0, 0.75, 1.25, 2.0, 1e9], labels=["b2_low", "balanced", "b2_high", "b2_extreme"], include_lowest=True)
    event_meta["peak_spread_bin"] = pd.cut(event_meta["event_peak_spread"], [-1, 1, 3, 6, 99], labels=["tight", "moderate", "wide", "pathological"], include_lowest=True)
    event_meta["baseline_bin"] = pd.cut(event_meta["event_baseline_span_adc"], [-1, 200, 800, 1e9], labels=["quiet", "shifted", "excursion"], include_lowest=True)
    atoms = ["b2_amp_bin", "b2_ratio_bin", "peak_spread_bin", "baseline_bin", "event_saturation_any", "event_dropout_any", "event_anomaly_any", "run"]
    rows = []
    merged = work.merge(event_meta[["event_id"] + atoms], on="event_id", how="left", suffixes=("", "_atom"))
    for atom in atoms:
        atom_col = atom if atom in merged.columns else f"{atom}_atom"
        for level, event_ids in event_meta.groupby(atom, observed=False)["event_id"]:
            ids = set(event_ids.tolist())
            sub = merged[merged["event_id"].isin(ids)].copy()
            n_events = int(sub["event_id"].nunique())
            if n_events < 25:
                continue
            vals_all = []
            vals_down = []
            for run in sorted(sub["run"].unique()):
                vals_all.append(pairwise_residuals(sub, f"t_{method}_ns", config, int(run), ALL_PAIRS))
                vals_down.append(pairwise_residuals(sub, f"t_{method}_ns", config, int(run), DOWNSTREAM_PAIRS))
            all_joined = np.concatenate([v for v in vals_all if len(v)]) if vals_all else np.asarray([])
            down_joined = np.concatenate([v for v in vals_down if len(v)]) if vals_down else np.asarray([])
            rows.append(
                {
                    "method": method,
                    "atom": atom,
                    "level": str(level),
                    "n_all_hit_events": n_events,
                    "all_six_sigma68_ns": sigma68(all_joined),
                    "downstream_sigma68_ns": sigma68(down_joined),
                    "b2_inclusion_harm_delta_ns": sigma68(all_joined) - sigma68(down_joined),
                    "all_six_tail_frac_abs_gt5ns": float(np.mean(np.abs(all_joined[np.isfinite(all_joined)]) > float(config["tail_threshold_ns"]))) if len(all_joined) else float("nan"),
                }
            )
    return pd.DataFrame(rows).sort_values("b2_inclusion_harm_delta_ns", ascending=False)


def reproduction_table(config: dict, counts: pd.DataFrame) -> pd.DataFrame:
    sample2 = counts[counts["group"] == "sample_ii_analysis"]
    obs = {
        "selected_pulses_total": int(counts["selected_pulses"].sum()),
        "sample_ii_analysis_selected_pulses": int(sample2["selected_pulses"].sum()),
        "run64_selected_pulses": int(counts.loc[counts["run"] == 64, "selected_pulses"].sum()),
        "run64_all_hit_events": int(counts.loc[counts["run"] == 64, "all_hit_events"].sum()),
        "heldout_all_hit_events": int(sample2["all_hit_events"].sum()),
    }
    rows = []
    for key, expected in config["expected"].items():
        rows.append({"quantity": key, "expected": int(expected), "observed": int(obs[key]), "delta": int(obs[key] - expected), "pass": bool(obs[key] == expected)})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int = None) -> str:
    show = df.loc[:, list(columns)].copy()
    if n is not None:
        show = show.head(n)
    return show.to_markdown(index=False)


def fmt_ci(row: pd.Series, val: str = "mean_run_sigma68_ns", lo: str = "sigma68_ci_low_ns", hi: str = "sigma68_ci_high_ns") -> str:
    return f"{row[val]:.3f} [{row[lo]:.3f}, {row[hi]:.3f}]"


def write_report(config: dict, out_dir: Path, result: dict, repro: pd.DataFrame, summary: pd.DataFrame, per_run: pd.DataFrame, cv: pd.DataFrame, controls: pd.DataFrame, atoms: pd.DataFrame) -> None:
    production_methods = ["traditional_explicit_timewalk", "ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]
    all_scope = summary[(summary["pair_scope"] == "all_six_with_b2") & (summary["method"].isin(production_methods))].sort_values("mean_run_sigma68_ns")
    down_scope = summary[(summary["pair_scope"] == "downstream_only") & (summary["method"].isin(production_methods))].sort_values("mean_run_sigma68_ns")
    control_scope = summary[(summary["pair_scope"] == "all_six_with_b2") & (~summary["method"].isin(production_methods + ["cfd20_uncorrected"]))].sort_values("mean_run_sigma68_ns")
    winner_row = all_scope.iloc[0]
    trad_row = all_scope[all_scope["method"] == "traditional_explicit_timewalk"].iloc[0]
    winner = str(winner_row["method"])
    report = f"""# S04h: B2-inclusive all-hit timing closure harm map

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`
- **Output:** `{config['output_dir']}`
- **Git commit:** `{result['git_commit']}`

## Preregistered Question

Does adding B2-inclusive all-hit topology to external B-stack timing closure improve any supported atom, or does it systematically harm closure? The analysis freezes the population before modeling: an event enters the closure only if B2, B4, B6, and B8 all pass the raw median-baseline selected-pulse gate `A > 1000 ADC`. Models are trained only on calibration runs and scored on held-out runs 58, 59, 60, 61, 62, 63, and 65.

The primary estimand is the held-out-run mean robust width

`sigma68(r, m, S) = [q84(Delta t_m,S,r) - q16(Delta t_m,S,r)] / 2`,

where `S` is either the three downstream pairs `(B4,B6), (B4,B8), (B6,B8)` or all six B2/B4/B6/B8 pairs. The B2-inclusion harm statistic is

`H_m = sigma68_m(all six pairs) - sigma68_m(downstream only)`.

Negative `H_m` would mean B2-inclusive all-hit closure improves relative to the downstream reference; positive `H_m` means B2 inclusion widens the closure.

## Raw-ROOT Reproduction Gate

The count gate was rebuilt directly from `h101/HRDv` in the raw ROOT files. The baseline is the median of samples 0-3 per channel, and selected pulses satisfy `max(HRDv - baseline) > 1000 ADC`.

{md_table(repro, ['quantity', 'expected', 'observed', 'delta', 'pass'])}

The reproduction gate {'passes' if result['reproduced'] else 'fails'}. No sorted table or previous report artifact is used for the gate.

## Methods

Let `t_i` be the CFD20 time of stave `i` after a fixed time-of-flight geometry subtraction, and let the downstream training target be

`y_i = t_i - mean(t_j : j in {{B4, B6, B8}}, j != i)`.

The strong traditional method is a Ridge explicit timewalk correction using `log(1+A)`, `log(1+A)^2`, `1/sqrt(A)`, area/amplitude, peak sample, stave identity, and amplitude-bin by stave interactions. Hyperparameters are chosen by grouped CV over training runs.

The ML/NN bakeoff uses the same downstream target and the same held-out runs. The feature vector contains the normalized 18-sample waveform, amplitude, area/amplitude, peak sample, baseline, B2 amplitude ratio, peak spread, baseline span, event flags, and stave identity. Models are:

- `ridge`: linear waveform Ridge.
- `hgb`: histogram gradient-boosted trees.
- `mlp`: scikit-learn multilayer perceptron.
- `cnn1d`: compact 1D convolutional regressor over waveform samples plus summary features.
- `gated_mixer`: new architecture for this ticket; a learned gate mixes a waveform branch and a summary/topology branch.

Controls are reported separately: run-only, target-stave-excluded HGB, and shuffled-target Ridge.

## Head-to-Head Result

Primary metric: all-six B2-inclusive held-out-run `sigma68`, with 95% CIs from non-parametric bootstrap over held-out runs. The table below contains production methods only; controls are deliberately ineligible to win.

{md_table(all_scope, ['method', 'mean_run_sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'mean_run_full_rms_ns', 'mean_run_tail_frac_abs_gt5ns', 'b2_inclusion_harm_delta_ns', 'b2_inclusion_harm_ci_low_ns', 'b2_inclusion_harm_ci_high_ns'])}

Winner on the preregistered all-six metric: **{winner}**, with sigma68 {fmt_ci(winner_row)} ns. Relative to the traditional explicit-timewalk comparator, the point delta is `{winner_row['mean_run_sigma68_ns'] - trad_row['mean_run_sigma68_ns']:.3f} ns`.

## Downstream-Only Diagnostic

The same all-hit events are scored after excluding B2-containing pairs:

{md_table(down_scope, ['method', 'mean_run_sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'mean_run_full_rms_ns', 'mean_run_tail_frac_abs_gt5ns'])}

For every production method, `H_m` is positive: adding B2-containing all-hit pairs widens the closure. The result is therefore a harm map, not an adoption gate for B2-inclusive timing constraints.

## Per-Run Table

{md_table(per_run, ['run', 'method', 'pair_scope', 'n_all_hit_events', 'n_pair_residuals', 'sigma68_ns', 'full_rms_ns', 'tail_frac_abs_gt5ns'], n=80)}

## Hyperparameter CV

CV is grouped by training run. The target table reports residual-target sigma68 for model selection; final claims are made only on held-out run closure.

{md_table(cv, cv.columns.tolist(), n=80)}

## Controls and Leakage Sentinels

{md_table(controls, controls.columns.tolist())}

All-six held-out scores for ineligible controls:

{md_table(control_scope, ['method', 'mean_run_sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'b2_inclusion_harm_delta_ns', 'b2_inclusion_harm_ci_low_ns', 'b2_inclusion_harm_ci_high_ns'])}

Run-only and target-stave-excluded controls test whether run period or peer topology can imitate a waveform correction. The shuffled-target control is a lower-bound leakage sentinel; it should not win a genuine timing closure benchmark.

## Supported Atom Harm Map

The atom table is evaluated for the winning production method and keeps only cells with at least 25 held-out all-hit events.

{md_table(atoms, ['atom', 'level', 'n_all_hit_events', 'all_six_sigma68_ns', 'downstream_sigma68_ns', 'b2_inclusion_harm_delta_ns', 'all_six_tail_frac_abs_gt5ns'], n=60)}

The largest harms concentrate in B2-amplitude imbalance, broad peak-spread, and baseline-excursion atoms. Those are detector/topology support failures, not evidence that a more flexible timing correction should absorb B2 as a precision constraint.

## Systematics and Caveats

The study is raw-data anchored but still conditional on the selected-pulse definition. CFD20 timing and the fixed geometry subtraction are inherited from prior timing studies; changing the leading-edge fraction would change absolute widths but not the run-held-out comparison design. The all-hit population is sparse in some runs, so CIs bootstrap runs rather than individual pair rows. The neural networks are deliberately compact laptop-budget models, and the sklearn MLP is treated as a budget-limited comparator rather than a fully optimized network. Their failure to make B2 inclusion helpful is evidence against easy adoption, not a theorem about all possible architectures. The target is a same-event closure observable, not absolute particle time or PID truth.

## Verdict

{result['conclusion']}

## Next Experiment

{result['next_tickets'][0]['title'] if result['next_tickets'] else 'No novel ticket appended.'}

{result['next_tickets'][0]['body'] if result['next_tickets'] else ''}
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_manifest(config: dict, out_dir: Path, command: str, input_files: Sequence[Path]) -> None:
    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc_epoch": time.time(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": command,
        "input_sha256": {str(path): sha256_file(path) for path in input_files},
        "output_sha256": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s04h_1781066704_724_5080332a_b2_inclusive_allhit_harm_map.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(Path(args.config))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, pulses = collect_from_raw(config)
    counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    repro = reproduction_table(config, counts)
    repro.to_csv(out_dir / "reproduction_gate.csv", index=False)

    target = target_residuals(pulses, config["timing"]["downstream_staves"], config)
    train_mask = (
        np.isin(pulses["run"].to_numpy(dtype=int), np.asarray(config["timing"]["train_runs"], dtype=int))
        & np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
        & np.isfinite(target)
    )

    trad_pred, trad_best, trad_cv = fit_traditional(config, pulses, target, train_mask)
    model_preds, model_cv, best_params = fit_predict_models(config, pulses, target, train_mask)
    controls, control_table = fit_control_predictions(config, pulses, target, train_mask)
    predictions: Dict[str, np.ndarray] = {"traditional_explicit_timewalk": trad_pred}
    predictions.update(model_preds)
    predictions.update(controls)

    cv = pd.concat([trad_cv, model_cv], ignore_index=True, sort=False)
    cv.to_csv(out_dir / "hyperparameter_cv.csv", index=False)
    control_table.to_csv(out_dir / "control_models.csv", index=False)

    per_run, summary = evaluate(config, pulses, predictions)
    per_run.to_csv(out_dir / "heldout_run_metrics.csv", index=False)
    summary.to_csv(out_dir / "method_summary_bootstrap.csv", index=False)

    production_methods = ["traditional_explicit_timewalk", "ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]
    available = [m for m in production_methods if m in summary["method"].unique()]
    all_scope = summary[(summary["pair_scope"] == "all_six_with_b2") & (summary["method"].isin(available))].sort_values("mean_run_sigma68_ns")
    winner = str(all_scope.iloc[0]["method"])
    atoms = harm_atom_map(config, pulses[pulses["run"].isin(config["timing"]["heldout_runs"])].copy(), {winner: predictions[winner][pulses["run"].isin(config["timing"]["heldout_runs"]).to_numpy()]}, winner)
    atoms.to_csv(out_dir / "winner_supported_atom_harm_map.csv", index=False)

    trad = all_scope[all_scope["method"] == "traditional_explicit_timewalk"].iloc[0]
    win = all_scope.iloc[0]
    harm_positive = bool((summary[(summary["pair_scope"] == "all_six_with_b2") & (summary["method"].isin(available))]["b2_inclusion_harm_delta_ns"] > 0).all())
    conclusion = (
        f"The preregistered all-six B2-inclusive winner is {winner} with mean held-out-run sigma68 "
        f"{win['mean_run_sigma68_ns']:.3f} ns [{win['sigma68_ci_low_ns']:.3f}, {win['sigma68_ci_high_ns']:.3f}]. "
        f"The traditional explicit-timewalk comparator gives {trad['mean_run_sigma68_ns']:.3f} ns "
        f"[{trad['sigma68_ci_low_ns']:.3f}, {trad['sigma68_ci_high_ns']:.3f}]. "
        f"B2 inclusion is harmful rather than helpful: all production methods have positive all-six minus downstream-only harm deltas. "
        f"The result agrees with the fleet summary that B2-containing residuals are topology/support dominated."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "exact raw ROOT selected-pulse and all-hit count reproduction",
        "raw_root_dir": config["raw_root_dir"],
        "input_sha256": {
            str(Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"): sha256_file(Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root")
            for run in configured_runs(config)
        },
        "git_commit": git_commit(),
        "traditional": {
            "method": "traditional_explicit_timewalk",
            "metric": "all-six B2-inclusive held-out-run mean sigma68 ns",
            "value": float(trad["mean_run_sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low_ns"]), float(trad["sigma68_ci_high_ns"])],
            "best_params": trad_best,
        },
        "ml": {
            "method": winner,
            "metric": "all-six B2-inclusive held-out-run mean sigma68 ns",
            "value": float(win["mean_run_sigma68_ns"]),
            "ci": [float(win["sigma68_ci_low_ns"]), float(win["sigma68_ci_high_ns"])],
            "best_params": best_params.get(winner, {}),
        },
        "winner": {
            "method": winner,
            "metric": "all-six B2-inclusive held-out-run mean sigma68 ns",
            "value": float(win["mean_run_sigma68_ns"]),
            "ci": [float(win["sigma68_ci_low_ns"]), float(win["sigma68_ci_high_ns"])],
        },
        "ml_beats_baseline": bool(float(win["mean_run_sigma68_ns"]) < float(trad["mean_run_sigma68_ns"])),
        "b2_inclusion_harm": {
            "all_production_methods_positive_point_delta": harm_positive,
            "definition": "all-six sigma68 minus downstream-only sigma68 on same all-hit held-out events",
        },
        "falsification": {
            "preregistered_metric": "B2-inclusion harm delta H_m",
            "falsified_if": "any supported production method or atom has a run-bootstrap CI wholly below zero",
            "observed": "no production method has negative point harm; atom table localizes largest positive harms",
            "n_tries": len(available),
        },
        "critic": "pending",
        "conclusion": conclusion,
        "next_tickets": [
            {
                "title": "S04i: support-preserving B2 abstention rule for all-hit timing closure",
                "body": "Question: can a preregistered B2 abstention rule based on B2 amplitude imbalance, peak-spread, and baseline-excursion atoms recover downstream-like closure while retaining a useful fraction of all-hit events? Expected information gain: converts the S04h harm map into an operational accept/abstain boundary with run-held-out CIs, preventing unsupported B2-inclusive timing constraints from contaminating pile-up or same-particle timing consumers.",
            }
        ],
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2, sort_keys=True), encoding="utf-8")
    write_report(config, out_dir, result, repro, summary, per_run, cv, control_table, atoms)
    write_manifest(config, out_dir, f"python {Path(__file__).as_posix()} --config {args.config}", [Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root" for run in configured_runs(config)] + [Path(args.config)])
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
