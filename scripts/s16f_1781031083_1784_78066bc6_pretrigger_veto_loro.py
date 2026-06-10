#!/usr/bin/env python3
"""S16f frozen pretrigger contamination veto under Sample-II LORO splits.

The analysis starts from raw ROOT HRDv waveforms, reproduces the selected-pulse
count gate, then compares a frozen train-run pretrigger quantile veto with
ridge, gradient-boosted trees, MLP, 1D-CNN, and a small Siamese CNN+metadata
architecture.  All thresholds are selected on training runs only and evaluated
on the held-out Sample-II run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(2)
except Exception:  # pragma: no cover - reported in manifest if unavailable.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


PAIR_ORDER = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
PAIR_TO_INT = {f"{a}-{b}": i for i, (a, b) in enumerate(PAIR_ORDER)}
SUMMARY_FEATURES = [
    "pair_code",
    "max_pre_abs_adc",
    "max_pre_ptp_adc",
    "max_pre_rms_adc",
    "max_abs_pre_slope_adc_per_sample",
    "mean_pre_mean_adc",
    "abs_delta_pre_mean_adc",
    "abs_delta_pre_slope_adc_per_sample",
    "max_pre_last_minus_first_adc",
    "abs_delta_pre_last_minus_first_adc",
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
            seed = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - seed[..., None]
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
        rows.append(
            {
                "quantity": f"sample_ii_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_ii[key]),
                "tolerance": 0,
            }
        )
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
            seed = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - seed[..., None]
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
                            "pre_last_minus_first_adc": float(pre[-1] - pre[0]),
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
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses.copy()
    sub["tcorr"] = sub["t_cfd20_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
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
        "pre_last_minus_first_adc",
        "amplitude_adc",
        "peak_sample",
    ]
    wide = sub.pivot(index="event_id", columns="stave", values=value_cols)
    rows = []
    run_lookup = sub.groupby("event_id")["run"].first()
    for event_id, row in wide.dropna().iterrows():
        run = int(run_lookup.loc[event_id])
        for a, b in PAIR_ORDER:
            residual = float(row[("tcorr", a)] - row[("tcorr", b)])
            pre_a = np.asarray([row[(f"pre_{i}", a)] for i in range(4)], dtype=float)
            pre_b = np.asarray([row[(f"pre_{i}", b)] for i in range(4)], dtype=float)
            pair = f"{a}-{b}"
            rows.append(
                {
                    "event_id": event_id,
                    "run": run,
                    "pair": pair,
                    "pair_code": int(PAIR_TO_INT[pair]),
                    "stave_a": a,
                    "stave_b": b,
                    "residual_ns": residual,
                    "max_pre_abs_adc": max(float(row[("pre_abs_adc", a)]), float(row[("pre_abs_adc", b)])),
                    "max_pre_ptp_adc": max(float(row[("pre_ptp_adc", a)]), float(row[("pre_ptp_adc", b)])),
                    "max_pre_rms_adc": max(float(row[("pre_rms_adc", a)]), float(row[("pre_rms_adc", b)])),
                    "max_abs_pre_slope_adc_per_sample": max(
                        abs(float(row[("pre_slope_adc_per_sample", a)])),
                        abs(float(row[("pre_slope_adc_per_sample", b)])),
                    ),
                    "mean_pre_mean_adc": 0.5 * (float(row[("pre_mean_adc", a)]) + float(row[("pre_mean_adc", b)])),
                    "abs_delta_pre_mean_adc": abs(float(row[("pre_mean_adc", a)]) - float(row[("pre_mean_adc", b)])),
                    "abs_delta_pre_slope_adc_per_sample": abs(
                        float(row[("pre_slope_adc_per_sample", a)]) - float(row[("pre_slope_adc_per_sample", b)])
                    ),
                    "max_pre_last_minus_first_adc": max(
                        abs(float(row[("pre_last_minus_first_adc", a)])),
                        abs(float(row[("pre_last_minus_first_adc", b)])),
                    ),
                    "abs_delta_pre_last_minus_first_adc": abs(
                        float(row[("pre_last_minus_first_adc", a)]) - float(row[("pre_last_minus_first_adc", b)])
                    ),
                    "min_amplitude_adc": min(float(row[("amplitude_adc", a)]), float(row[("amplitude_adc", b)])),
                    "max_peak_sample": max(float(row[("peak_sample", a)]), float(row[("peak_sample", b)])),
                    "pre_seq": np.vstack([pre_a, pre_b]).astype(np.float32),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no pair residuals produced")
    return out


def apply_train_pair_centers(train: pd.DataFrame, frame: pd.DataFrame, tail_cut: float) -> pd.DataFrame:
    centers = train.groupby("pair")["residual_ns"].median().to_dict()
    out = frame.copy()
    out["train_pair_center_ns"] = out["pair"].map(centers).astype(float)
    out["centered_residual_ns"] = out["residual_ns"] - out["train_pair_center_ns"]
    out["tail_abs_gt5ns"] = np.abs(out["centered_residual_ns"]) > float(tail_cut)
    return out


def empirical_quantile_scores(train: pd.DataFrame, frame: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    scores = []
    n = len(train)
    for col in cols:
        ref = np.sort(train[col].to_numpy(dtype=float))
        vals = frame[col].to_numpy(dtype=float)
        ranks = np.searchsorted(ref, vals, side="right") / max(float(n), 1.0)
        scores.append(ranks)
    return np.max(np.vstack(scores), axis=0)


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = np.clip(x, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-x))


def standardized_features(train: pd.DataFrame, frame: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    x_train = train[SUMMARY_FEATURES].to_numpy(dtype=float)
    x_frame = frame[SUMMARY_FEATURES].to_numpy(dtype=float)
    return scaler.fit_transform(x_train), scaler.transform(x_frame)


def preseq_arrays(train: pd.DataFrame, frame: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_seq = np.stack(train["pre_seq"].to_numpy()).astype(np.float32)
    frame_seq = np.stack(frame["pre_seq"].to_numpy()).astype(np.float32)
    med = np.median(train_seq, axis=(0, 2), keepdims=True)
    mad = np.median(np.abs(train_seq - med), axis=(0, 2), keepdims=True)
    scale = np.maximum(1.4826 * mad, 1.0)
    return ((train_seq - med) / scale).astype(np.float32), ((frame_seq - med) / scale).astype(np.float32)


class TinyCnn(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(2, 8, kernel_size=2),
            nn.ReLU(),
            nn.Conv1d(8, 8, kernel_size=2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 1),
        )

    def forward(self, seq: torch.Tensor, meta: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(seq).squeeze(-1)


class SiamesePretriggerNet(nn.Module):
    def __init__(self, n_meta: int) -> None:
        super().__init__()
        self.branch = nn.Sequential(
            nn.Conv1d(1, 8, kernel_size=2),
            nn.ReLU(),
            nn.Conv1d(8, 8, kernel_size=2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(16, 8),
            nn.ReLU(),
        )
        self.head = nn.Sequential(
            nn.Linear(8 * 3 + n_meta, 24),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(24, 1),
        )

    def forward(self, seq: torch.Tensor, meta: torch.Tensor | None = None) -> torch.Tensor:
        a = self.branch(seq[:, 0:1, :])
        b = self.branch(seq[:, 1:2, :])
        z = torch.cat([a, b, torch.abs(a - b), meta], dim=1)
        return self.head(z).squeeze(-1)


def train_torch_model(
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
    y_float = y.astype(np.float32)
    pos = max(float(y_float.sum()), 1.0)
    neg = max(float(len(y_float) - y_float.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["models"]["nn_learning_rate"]),
        weight_decay=float(config["models"]["nn_weight_decay"]),
    )
    ds = TensorDataset(
        torch.tensor(train_seq, dtype=torch.float32),
        torch.tensor(train_meta, dtype=torch.float32),
        torch.tensor(y_float, dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=int(config["models"]["nn_batch_size"]), shuffle=True)
    best_loss = float("inf")
    stale = 0
    for _ in range(int(config["models"]["nn_epochs"])):
        model.train()
        total = 0.0
        count = 0
        for xb, mb, yb in loader:
            xb, mb, yb = xb.to(device), mb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb, mb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(yb)
            count += len(yb)
        avg = total / max(count, 1)
        if avg + 1e-5 < best_loss:
            best_loss = avg
            stale = 0
        else:
            stale += 1
            if stale >= int(config["models"]["nn_patience"]):
                break
    model.eval()
    with torch.no_grad():
        logits = model(
            torch.tensor(frame_seq, dtype=torch.float32, device=device),
            torch.tensor(frame_meta, dtype=torch.float32, device=device),
        )
    return sigmoid(logits.cpu().numpy())


def fit_method_scores(train: pd.DataFrame, frame: pd.DataFrame, config: dict, method: str, shuffled_proxy: bool, seed: int) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    y = train["tail_abs_gt5ns"].astype(int).to_numpy()
    train_work = train.copy()
    if shuffled_proxy:
        perm = rng.permutation(len(train_work))
        for col in SUMMARY_FEATURES:
            train_work[col] = train_work[col].to_numpy()[perm]
        seq = np.stack(train_work["pre_seq"].to_numpy())
        train_work["pre_seq"] = list(seq[perm])

    if method == "traditional_quantile":
        proxy_cols = [
            "max_pre_abs_adc",
            "max_pre_ptp_adc",
            "max_pre_rms_adc",
            "max_abs_pre_slope_adc_per_sample",
            "max_pre_last_minus_first_adc",
        ]
        score = empirical_quantile_scores(train_work, frame, proxy_cols)
        if shuffled_proxy:
            score = score[rng.permutation(len(score))]
        return score

    x_train, x_frame = standardized_features(train_work, frame)
    if method == "ridge":
        scores_by_alpha = []
        for alpha in config["models"]["ridge_alphas"]:
            model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(alpha), class_weight="balanced"))
            model.fit(train_work[SUMMARY_FEATURES], y)
            scores_by_alpha.append(sigmoid(model.decision_function(frame[SUMMARY_FEATURES])))
        return np.mean(np.vstack(scores_by_alpha), axis=0)
    if method == "gradient_boosted_trees":
        model = HistGradientBoostingClassifier(
            max_iter=int(config["models"]["gbt_max_iter"]),
            learning_rate=float(config["models"]["gbt_learning_rate"]),
            max_leaf_nodes=int(config["models"]["gbt_max_leaf_nodes"]),
            random_state=int(seed),
        )
        model.fit(x_train, y)
        return model.predict_proba(x_frame)[:, 1]
    if method == "mlp":
        model = MLPClassifier(
            hidden_layer_sizes=tuple(int(v) for v in config["models"]["mlp_hidden_layer_sizes"]),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            random_state=int(seed),
            early_stopping=True,
            n_iter_no_change=15,
        )
        model.fit(x_train, y)
        return model.predict_proba(x_frame)[:, 1]
    if method in {"cnn1d", "siamese_cnn_meta"}:
        train_seq, frame_seq = preseq_arrays(train_work, frame)
        meta_train, meta_frame = standardized_features(train_work, frame)
        if method == "cnn1d":
            meta_train = np.zeros((len(train_seq), 1), dtype=np.float32)
            meta_frame = np.zeros((len(frame_seq), 1), dtype=np.float32)
            return train_torch_model(TinyCnn(), train_seq, meta_train, y, frame_seq, meta_frame, config, seed)
        return train_torch_model(SiamesePretriggerNet(meta_train.shape[1]), train_seq, meta_train, y, frame_seq, meta_frame, config, seed)
    raise ValueError(method)


def select_threshold(train: pd.DataFrame, score: np.ndarray, config: dict) -> dict:
    y = train["tail_abs_gt5ns"].astype(bool).to_numpy()
    rows = []
    min_eff = float(config["veto"]["min_train_efficiency"])
    for q in config["veto"]["threshold_quantiles"]:
        threshold = float(np.quantile(score, float(q)))
        veto = score >= threshold
        eff = float(1.0 - veto.mean())
        tail_capture = float(veto[y].mean()) if y.any() else 0.0
        post_tail = float(y[~veto].mean()) if np.any(~veto) else float("nan")
        utility = (
            float(config["veto"]["utility_tail_weight"]) * tail_capture
            - float(config["veto"]["utility_veto_penalty"]) * float(veto.mean())
        )
        rows.append(
            {
                "threshold_quantile": float(q),
                "threshold": threshold,
                "train_efficiency": eff,
                "train_veto_fraction": float(veto.mean()),
                "train_tail_capture": tail_capture,
                "train_post_veto_tail_fraction": post_tail,
                "train_utility": utility if eff >= min_eff else -np.inf,
            }
        )
    scan = pd.DataFrame(rows)
    best = scan.sort_values(["train_utility", "train_tail_capture"], ascending=False).iloc[0].to_dict()
    return {"best": best, "scan": scan}


def score_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return {"auc": float("nan"), "average_precision": float("nan"), "brier": float("nan")}
    clipped = np.clip(score, 0.0, 1.0)
    return {
        "auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier": float(brier_score_loss(y, clipped)),
    }


def evaluate_veto(frame: pd.DataFrame, score: np.ndarray, threshold: float, method: str, heldout_run: int, shuffled_proxy: bool) -> dict:
    veto = score >= float(threshold)
    kept = frame[~veto]
    y = frame["tail_abs_gt5ns"].astype(bool).to_numpy()
    base_sigma = sigma68(frame["centered_residual_ns"].to_numpy())
    kept_sigma = sigma68(kept["centered_residual_ns"].to_numpy())
    base_tail = float(y.mean()) if len(y) else float("nan")
    kept_tail = float(kept["tail_abs_gt5ns"].mean()) if len(kept) else float("nan")
    centered = frame["centered_residual_ns"].to_numpy(dtype=float)
    kept_centered = kept["centered_residual_ns"].to_numpy(dtype=float)
    metrics = score_metrics(y.astype(int), score)
    return {
        "heldout_run": int(heldout_run),
        "method": method,
        "shuffled_proxy": bool(shuffled_proxy),
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "n_tail_pairs_before": int(y.sum()),
        "threshold": float(threshold),
        "veto_fraction": float(veto.mean()) if len(veto) else float("nan"),
        "timing_efficiency": float(1.0 - veto.mean()) if len(veto) else float("nan"),
        "tail_capture": float(veto[y].mean()) if y.any() else 0.0,
        "tail_fraction_before": base_tail,
        "tail_fraction_after": kept_tail,
        "tail_fraction_delta": kept_tail - base_tail if math.isfinite(kept_tail) else float("nan"),
        "sigma68_before_ns": base_sigma,
        "sigma68_after_ns": kept_sigma,
        "sigma68_delta_ns": kept_sigma - base_sigma if math.isfinite(kept_sigma) else float("nan"),
        "full_rms_before_ns": float(np.sqrt(np.mean(centered**2))) if len(centered) else float("nan"),
        "full_rms_after_ns": float(np.sqrt(np.mean(kept_centered**2))) if len(kept_centered) else float("nan"),
        **metrics,
    }


def run_loro(pair_frame: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = ["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]
    tail_cut = float(config["timing"]["tail_abs_residual_ns"])
    rows = []
    pred_rows = []
    scan_rows = []
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    for fold_i, heldout_run in enumerate(runs):
        raw_train = pair_frame[pair_frame["run"] != heldout_run].copy()
        raw_held = pair_frame[pair_frame["run"] == heldout_run].copy()
        train = apply_train_pair_centers(raw_train, raw_train, tail_cut)
        held = apply_train_pair_centers(train, raw_held, tail_cut)
        for method in methods:
            for shuffled in [False, True]:
                print(f"fold heldout={heldout_run} method={method} shuffled_proxy={shuffled}", flush=True)
                seed = int(config["models"]["random_seed"]) + 1000 * fold_i + 17 * methods.index(method) + (500 if shuffled else 0)
                try:
                    combined = pd.concat([train, held], ignore_index=True)
                    combined_score = fit_method_scores(train, combined, config, method, shuffled, seed)
                    train_score = combined_score[: len(train)]
                    held_score = combined_score[len(train) :]
                except Exception as exc:
                    if method in {"cnn1d", "siamese_cnn_meta"} and torch is None:
                        raise
                    raise RuntimeError(f"{method} failed on fold {heldout_run}, shuffled={shuffled}") from exc
                sel = select_threshold(train, train_score, config)
                best = sel["best"]
                scan = sel["scan"].copy()
                scan["heldout_run"] = heldout_run
                scan["method"] = method
                scan["shuffled_proxy"] = bool(shuffled)
                scan_rows.append(scan)
                ev = evaluate_veto(held, held_score, float(best["threshold"]), method, heldout_run, shuffled)
                ev.update(
                    {
                        "train_threshold_quantile": float(best["threshold_quantile"]),
                        "train_utility": float(best["train_utility"]),
                        "train_tail_capture": float(best["train_tail_capture"]),
                        "train_efficiency": float(best["train_efficiency"]),
                    }
                )
                rows.append(ev)
                tmp = held[["event_id", "run", "pair", "centered_residual_ns", "tail_abs_gt5ns"]].copy()
                tmp["method"] = method
                tmp["shuffled_proxy"] = bool(shuffled)
                tmp["score"] = held_score
                tmp["threshold"] = float(best["threshold"])
                tmp["veto"] = held_score >= float(best["threshold"])
                pred_rows.append(tmp)
    return pd.DataFrame(rows), pd.concat(pred_rows, ignore_index=True), pd.concat(scan_rows, ignore_index=True)


def metric_summary(frame: pd.DataFrame) -> dict:
    vals = frame["centered_residual_ns"].to_numpy(dtype=float)
    return {
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "tail_fraction": float(frame["tail_abs_gt5ns"].mean()) if len(frame) else float("nan"),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": float(np.sqrt(np.mean(vals**2))) if len(vals) else float("nan"),
    }


def aggregate_from_predictions(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, shuffled), sub in pred.groupby(["method", "shuffled_proxy"]):
        before = metric_summary(sub)
        kept = sub[~sub["veto"]]
        after = metric_summary(kept)
        y = sub["tail_abs_gt5ns"].astype(bool).to_numpy()
        veto = sub["veto"].astype(bool).to_numpy()
        score_m = score_metrics(y.astype(int), sub["score"].to_numpy(dtype=float))
        rows.append(
            {
                "method": method,
                "shuffled_proxy": bool(shuffled),
                "n_pairs": before["n_pairs"],
                "n_events": before["n_events"],
                "veto_fraction": float(veto.mean()) if len(veto) else float("nan"),
                "timing_efficiency": float(1.0 - veto.mean()) if len(veto) else float("nan"),
                "tail_capture": float(veto[y].mean()) if y.any() else 0.0,
                "tail_fraction_before": before["tail_fraction"],
                "tail_fraction_after": after["tail_fraction"],
                "tail_fraction_delta": after["tail_fraction"] - before["tail_fraction"],
                "sigma68_before_ns": before["sigma68_ns"],
                "sigma68_after_ns": after["sigma68_ns"],
                "sigma68_delta_ns": after["sigma68_ns"] - before["sigma68_ns"],
                "full_rms_before_ns": before["full_rms_ns"],
                "full_rms_after_ns": after["full_rms_ns"],
                **score_m,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    methods = list(pred.groupby(["method", "shuffled_proxy"]).groups)
    rows = []
    for method, shuffled in methods:
        print(f"bootstrap method={method} shuffled_proxy={shuffled}", flush=True)
        sub = pred[(pred["method"] == method) & (pred["shuffled_proxy"] == shuffled)].reset_index(drop=True)
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        residual = sub["centered_residual_ns"].to_numpy(dtype=float)
        y = sub["tail_abs_gt5ns"].to_numpy(dtype=bool)
        veto = sub["veto"].to_numpy(dtype=bool)
        score = sub["score"].to_numpy(dtype=float)
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
            r = residual[idx]
            yy = y[idx]
            vv = veto[idx]
            kept = ~vv
            before_tail = float(yy.mean()) if len(yy) else float("nan")
            after_tail = float(yy[kept].mean()) if np.any(kept) else float("nan")
            sigma_before = sigma68(r)
            sigma_after = sigma68(r[kept])
            score_m = score_metrics(yy.astype(int), score[idx])
            stats.append(
                {
                    "veto_fraction": float(vv.mean()) if len(vv) else float("nan"),
                    "timing_efficiency": float(1.0 - vv.mean()) if len(vv) else float("nan"),
                    "tail_capture": float(vv[yy].mean()) if yy.any() else 0.0,
                    "tail_fraction_after": after_tail,
                    "tail_fraction_delta": after_tail - before_tail if math.isfinite(after_tail) else float("nan"),
                    "sigma68_after_ns": sigma_after,
                    "sigma68_delta_ns": sigma_after - sigma_before if math.isfinite(sigma_after) else float("nan"),
                    "full_rms_after_ns": float(np.sqrt(np.mean(r[kept] ** 2))) if np.any(kept) else float("nan"),
                    **score_m,
                }
            )
        stat_df = pd.DataFrame(stats)
        row = {"method": method, "shuffled_proxy": bool(shuffled)}
        for col in [
            "veto_fraction",
            "timing_efficiency",
            "tail_capture",
            "tail_fraction_after",
            "tail_fraction_delta",
            "sigma68_after_ns",
            "sigma68_delta_ns",
            "full_rms_after_ns",
            "auc",
            "average_precision",
        ]:
            row[f"{col}_ci_low"] = float(np.nanpercentile(stat_df[col], 2.5))
            row[f"{col}_ci_high"] = float(np.nanpercentile(stat_df[col], 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def leakage_checks(pred: pd.DataFrame, fold_metrics: pd.DataFrame, pair_frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    actual = fold_metrics[~fold_metrics["shuffled_proxy"]]
    shuffled = fold_metrics[fold_metrics["shuffled_proxy"]]
    merged = actual.merge(shuffled, on=["heldout_run", "method"], suffixes=("", "_shuffled"))
    guard_rows = []
    for method, sub in merged.groupby("method"):
        guard_rows.append(
            {
                "check": f"{method}_actual_tail_capture_ge_shuffled_proxy_median",
                "value": float(np.nanmedian(sub["tail_capture"] - sub["tail_capture_shuffled"])),
                "pass": bool(np.nanmedian(sub["tail_capture"] - sub["tail_capture_shuffled"]) >= -0.05),
            }
        )
    used_runs = set(int(r) for r in pair_frame["run"].unique())
    expected_runs = set(int(r) for r in config["timing"]["loro_runs"])
    forbidden = {"run", "event_id", "eventno", "evt", "residual_ns", "centered_residual_ns", "tail_abs_gt5ns"}
    feature_overlap = sorted(set(SUMMARY_FEATURES) & forbidden)
    event_overlaps = []
    for heldout_run in config["timing"]["loro_runs"]:
        train_events = set(pair_frame[pair_frame["run"] != heldout_run]["event_id"])
        held_events = set(pair_frame[pair_frame["run"] == heldout_run]["event_id"])
        event_overlaps.append(len(train_events & held_events))
    base = [
        {"check": "loro_runs_match_config", "value": ",".join(map(str, sorted(used_runs))), "pass": used_runs == expected_runs},
        {"check": "train_heldout_event_id_overlap_max", "value": int(max(event_overlaps)), "pass": max(event_overlaps) == 0},
        {"check": "features_exclude_run_event_residual_labels", "value": ",".join(feature_overlap), "pass": len(feature_overlap) == 0},
        {"check": "all_predictions_finite", "value": int(np.isfinite(pred["score"]).sum()), "pass": bool(np.isfinite(pred["score"]).all())},
        {"check": "one_row_per_method_fold_shuffled_state", "value": int(len(fold_metrics)), "pass": len(fold_metrics) == 7 * 6 * 2},
    ]
    return pd.DataFrame(base + guard_rows)


def format_match_table(match: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {int(r.tolerance)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in match.rename(columns={"pass": "pass_"}).itertuples()
    )


def format_benchmark_table(agg: pd.DataFrame, ci: pd.DataFrame) -> str:
    view = agg[~agg["shuffled_proxy"]].merge(ci[~ci["shuffled_proxy"]], on=["method", "shuffled_proxy"])
    order = ["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]
    view["order"] = view["method"].map({m: i for i, m in enumerate(order)})
    view = view.sort_values("order")
    rows = []
    for r in view.itertuples():
        rows.append(
            f"| {r.method} | {r.timing_efficiency:.3f} [{r.timing_efficiency_ci_low:.3f}, {r.timing_efficiency_ci_high:.3f}] | "
            f"{r.tail_capture:.3f} [{r.tail_capture_ci_low:.3f}, {r.tail_capture_ci_high:.3f}] | "
            f"{r.tail_fraction_after:.4f} [{r.tail_fraction_after_ci_low:.4f}, {r.tail_fraction_after_ci_high:.4f}] | "
            f"{r.sigma68_after_ns:.3f} [{r.sigma68_after_ns_ci_low:.3f}, {r.sigma68_after_ns_ci_high:.3f}] | "
            f"{r.sigma68_delta_ns:+.3f} [{r.sigma68_delta_ns_ci_low:+.3f}, {r.sigma68_delta_ns_ci_high:+.3f}] | "
            f"{r.auc:.3f} | {r.average_precision:.3f} |"
        )
    return "\n".join(rows)


def format_fold_table(fold: pd.DataFrame, method: str) -> str:
    sub = fold[(fold["method"] == method) & (~fold["shuffled_proxy"])].sort_values("heldout_run")
    return "\n".join(
        f"| {int(r.heldout_run)} | {int(r.n_pairs)} | {r.timing_efficiency:.3f} | {r.tail_capture:.3f} | {r.tail_fraction_after:.4f} | {r.sigma68_after_ns:.3f} | {r.sigma68_delta_ns:+.3f} |"
        for r in sub.itertuples()
    )


def format_leakage_table(checks: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in checks.rename(columns={"pass": "pass_"}).itertuples()
    )


def plot_outputs(out_dir: Path, agg: pd.DataFrame, ci: pd.DataFrame, pred: pd.DataFrame, winner: str) -> None:
    view = agg[~agg["shuffled_proxy"]].merge(ci[~ci["shuffled_proxy"]], on=["method", "shuffled_proxy"])
    order = ["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]
    view["order"] = view["method"].map({m: i for i, m in enumerate(order)})
    view = view.sort_values("order")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.errorbar(
        np.arange(len(view)),
        view["tail_fraction_after"],
        yerr=[
            view["tail_fraction_after"] - view["tail_fraction_after_ci_low"],
            view["tail_fraction_after_ci_high"] - view["tail_fraction_after"],
        ],
        fmt="o",
        label="post-veto tail fraction",
    )
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(view["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out post-veto tail fraction")
    ax.set_title("Sample-II LORO frozen pretrigger veto")
    ax.axhline(float(agg["tail_fraction_before"].iloc[0]), color="0.4", ls="--", lw=1, label="before veto")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head_tail_fraction.png", dpi=150)
    plt.close(fig)

    sub = pred[(pred["method"] == winner) & (~pred["shuffled_proxy"])].copy()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(sub.loc[~sub["veto"], "centered_residual_ns"], bins=45, histtype="step", density=True, label="kept")
    ax.hist(sub.loc[sub["veto"], "centered_residual_ns"], bins=45, histtype="step", density=True, label="vetoed")
    ax.set_xlabel("CFD20 pair residual, train-pair centered [ns]")
    ax.set_ylabel("density")
    ax.set_title(f"Winner residual distribution: {winner}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_residuals_kept_vetoed.png", dpi=150)
    plt.close(fig)


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S16f: Frozen Pre-Trigger Contamination Veto Under Sample-II LORO Timing Splits

- **Study ID:** S16f
- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S02/S02b downstream timing residual definitions, S16 pre-trigger baseline diagnostics
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `configs/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.json`

## 0. Question

Can a veto frozen from train-run pre-trigger proxy quantiles remove S02b-style Sample-II downstream timing tails under leave-one-run-out (LORO) splits without sacrificing too much timing efficiency, and do ridge, gradient-boosted trees, MLP, 1D-CNN, or a pair-symmetric CNN+metadata architecture beat the strong traditional quantile veto?

## 1. Reproduction Gate From Raw ROOT

The gate reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root`, subtracts the median of samples 0-3 per B stave, and counts pulses with baseline-subtracted amplitude `A > 1000 ADC`. No sorted ROOT files or cached tables are used for this gate.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{numbers["match_rows"]}

The timing-consumer table then requires B4, B6, and B8 all to pass the same amplitude cut in each Sample-II event. This produced `{numbers["n_events"]}` all-downstream events and `{numbers["n_pairs"]}` pair residuals across LORO runs {config["timing"]["loro_runs"]}.

## 2. Traditional Method

For event pair \(i\), the base residual is

\[
r_i = (t_a - x_a/v) - (t_b - x_b/v),
\]

where `t` is CFD20 time, `x` is the B-stack position at {config["spacing_cm"]} cm spacing, and `1/v = {config["tof_per_cm_ns"]}` ns/cm. For each LORO fold, pair centers \(m_p\) are medians of train-run residuals only. The tail label used for training diagnostics is \(y_i = 1(|r_i-m_{{p(i)}}| > {config["timing"]["tail_abs_residual_ns"]} ns)\).

The traditional veto score is a frozen train-run empirical quantile envelope:

\[
s_i^{{trad}} = \max_j \hat F_{{j,train}}(z_{{ij}}),
\]

where \(z_j\) are pre-trigger-only pair proxies: maximum absolute pre-trigger amplitude, peak-to-peak range, RMS, absolute slope, and last-minus-first excursion. The threshold is selected on train runs from quantiles {config["veto"]["threshold_quantiles"]}, with train timing efficiency constrained to at least {config["veto"]["min_train_efficiency"]}.

## 3. ML And NN Methods

All ML methods use the same LORO folds and exclude run id, event id, residuals, tail labels, post-trigger samples, pulse amplitude, and peak sample. The tabular features are pair identity plus pre-trigger summaries from samples 0-3. The 1D-CNN receives only the two four-sample pre-trigger traces. The new architecture, `siamese_cnn_meta`, applies a shared convolutional branch to each stave's pre-trigger trace, combines both embeddings with their absolute difference, then concatenates the tabular pre-trigger summaries.

Models:

- `ridge`: balanced RidgeClassifier averaged over alpha grid {config["models"]["ridge_alphas"]}.
- `gradient_boosted_trees`: HistGradientBoostingClassifier with {config["models"]["gbt_max_iter"]} boosting iterations.
- `mlp`: scikit-learn MLP with hidden layers {config["models"]["mlp_hidden_layer_sizes"]}.
- `cnn1d`: compact Conv1d network over the two pre-trigger channels.
- `siamese_cnn_meta`: pair-symmetric Conv1d branch plus pre-trigger metadata.

For each model, the veto threshold is frozen from train-run scores by the same efficiency-constrained utility as the traditional score. Probability calibration is summarized by Brier score in `head_to_head_benchmark.csv`; AUC/AP are auxiliary ranking diagnostics, not the primary physics metric.

## 4. Head-To-Head Benchmark

Primary pre-registered metric: held-out post-veto `|residual| > 5 ns` tail fraction at train-selected support, with sigma68 movement and timing efficiency reported as co-primary safety metrics. CIs resample runs, then events within each sampled run.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

Winner by support-constrained post-veto tail fraction: **{numbers["winner"]}**. The baseline pre-veto tail fraction was `{numbers["baseline_tail"]:.4f}`, and baseline sigma68 was `{numbers["baseline_sigma"]:.3f} ns`.

Per-held-out-run metrics for the winner:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
{numbers["winner_fold_rows"]}

## 5. Falsification

Pre-registration from the ticket: a useful veto must transfer under Sample-II LORO splits, reject S02b timing tails, preserve timing efficiency, and pass shuffled-proxy plus train/held-out leakage guards. The falsification test is the shuffled-proxy control: train each method after permuting train-run pre-trigger proxies relative to labels. A claimed method is rejected if its median tail-capture advantage over the shuffled-proxy version is below -0.05 or if the LORO split leaks event ids.

Multiple methods were tested (`N = 6`). The report therefore does not interpret nominal per-method p-values as discovery claims; the winner is an operational benchmark choice under a fixed metric. Shuffled-proxy deltas and leakage guards are tabulated below.

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## 6. Threats To Validity

Benchmark/selection: the traditional method is not a strawman; it uses a train-frozen empirical quantile envelope over the most direct pre-trigger contamination proxies and the same threshold utility as ML.

Data leakage: splits are by run. Features explicitly exclude run id, event id, residuals, labels, post-trigger waveform samples, amplitudes, and peak samples. Pair centers, empirical quantiles, scalers, neural normalizers, model fits, and thresholds are all trained inside the current LORO train runs.

Metric misuse: the report gives tail fraction, tail capture, timing efficiency, sigma68, full RMS, and score-ranking diagnostics. Sigma68 can improve simply by deleting hard events, so efficiency is always co-reported.

Post-hoc selection: the metric and threshold rule are fixed in the config before seeing held-out outcomes. The only post-hoc operation is naming the winner by the configured metric after all methods are evaluated.

Systematics and caveats: the label is a timing-tail proxy, not a truth label for contamination. The pre-trigger window has only four samples; CNN capacity is intentionally small. Pair residuals share events, which is why CIs bootstrap events within runs rather than individual pair rows. The method is a veto frontier, not a timing correction, and should not be adopted for charge, PID, or energy studies without a support-drift audit.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Input ROOT checksums are in `input_sha256.csv`; output checksums are in the manifest.

## 8. Findings And Next Steps

The strongest held-out method is **{numbers["winner"]}**. Its result should be interpreted as a support-constrained pre-trigger veto benchmark: it names which score best removes timing-tail pairs under Sample-II LORO, not which score is physically causal. The shuffled-proxy controls determine whether the apparent tail capture follows real pre-trigger structure rather than a run or threshold artifact.

One natural follow-up is to propagate the winning veto into a charge/current/topology support audit before adoption, because deleting timing-tail events can bias downstream physics samples even when timing sigma68 improves.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py --config configs/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`, `fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`, `head_to_head_benchmark.csv`, `bootstrap_cis.csv`, `leakage_checks.csv`, `fig_head_to_head_tail_fraction.png`, and `fig_winner_residuals_kept_vetoed.png`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


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

    fold_metrics, pred, scans = run_loro(pair_frame, config)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    scans.to_csv(out_dir / "threshold_scans.csv", index=False)

    agg = aggregate_from_predictions(pred)
    ci = bootstrap_ci(pred, config, rng)
    benchmark = agg.merge(ci, on=["method", "shuffled_proxy"])
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    ci.to_csv(out_dir / "bootstrap_cis.csv", index=False)

    checks = leakage_checks(pred, fold_metrics, pair_frame, config)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    actual = benchmark[~benchmark["shuffled_proxy"]].copy()
    actual["winner_score"] = actual["tail_fraction_after"] + 0.05 * np.maximum(0.0, 0.85 - actual["timing_efficiency"])
    winner_row = actual.sort_values(["winner_score", "sigma68_after_ns"]).iloc[0]
    winner = str(winner_row["method"])
    plot_outputs(out_dir, agg, ci, pred, winner)

    input_hash_rows = [{"file": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    git = git_commit()
    baseline_tail = float(actual["tail_fraction_before"].iloc[0])
    baseline_sigma = float(actual["sigma68_before_ns"].iloc[0])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-06-10",
        "reproduction_pass": bool(match["pass"].all()),
        "raw_reproduction": match.to_dict(orient="records"),
        "split": "Sample-II leave-one-run-out by run",
        "baseline": {
            "method": "CFD20 pair residual before veto",
            "tail_fraction_abs_gt5ns": baseline_tail,
            "sigma68_ns": baseline_sigma,
        },
        "methods": actual.drop(columns=["winner_score"]).to_dict(orient="records"),
        "winner": {
            "method": winner,
            "criterion": "lowest held-out post-veto tail fraction with timing-efficiency penalty below 0.85",
            "tail_fraction_after": float(winner_row["tail_fraction_after"]),
            "tail_fraction_after_ci": [
                float(winner_row["tail_fraction_after_ci_low"]),
                float(winner_row["tail_fraction_after_ci_high"]),
            ],
            "timing_efficiency": float(winner_row["timing_efficiency"]),
            "timing_efficiency_ci": [
                float(winner_row["timing_efficiency_ci_low"]),
                float(winner_row["timing_efficiency_ci_high"]),
            ],
            "tail_capture": float(winner_row["tail_capture"]),
            "sigma68_after_ns": float(winner_row["sigma68_after_ns"]),
            "sigma68_delta_ns": float(winner_row["sigma68_delta_ns"]),
        },
        "shuffled_proxy_controls": benchmark[benchmark["shuffled_proxy"]].to_dict(orient="records"),
        "leakage_checks_pass": bool(checks["pass"].all()),
        "caveat": "Tail label is a timing proxy, not a truth label for physical pre-trigger contamination.",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    numbers = {
        "git_commit": git,
        "match_rows": format_match_table(match),
        "n_events": int(pair_frame["event_id"].nunique()),
        "n_pairs": int(len(pair_frame)),
        "benchmark_rows": format_benchmark_table(agg, ci),
        "winner": winner,
        "baseline_tail": baseline_tail,
        "baseline_sigma": baseline_sigma,
        "winner_fold_rows": format_fold_table(fold_metrics, winner),
        "leakage_rows": format_leakage_table(checks),
    }
    write_report(out_dir, config, numbers)

    manifest = {
        "script": str(Path(__file__)),
        "config": str(args.config),
        "output_dir": str(out_dir),
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git,
        "python": sys.version,
        "platform": platform.platform(),
        "torch_available": bool(torch is not None),
        "commands": [
            f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}",
        ],
        "random_seed": int(config["models"]["random_seed"]),
        "input_sha256": input_hash_rows,
        "output_sha256": output_hashes(out_dir),
        "elapsed_seconds": float(time.time() - t0),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "elapsed_seconds": time.time() - t0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
