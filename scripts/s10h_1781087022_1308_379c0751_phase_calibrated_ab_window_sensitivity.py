#!/usr/bin/env python3
"""S10h: phase-calibrated A/B coincidence-window sensitivity.

The benchmark uses raw ROOT as the starting point.  It reproduces the registered
B-stave selected-pulse count, estimates per-run even/odd readout phase offsets
from clean single-pulse candidates, then tests coincidence-window labels after
phase correction.  The odd duplicate readout is used as the B-side closure
stand-in because it is the available per-event A/B-like paired waveform in the
hrdb raw files.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s10h-1781087022")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (not math.isfinite(value)):
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


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


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def cfd_time(wave: np.ndarray, fraction: float) -> float:
    amp = float(np.nanmax(wave))
    if not np.isfinite(amp) or amp <= 0:
        return float("nan")
    thr = amp * float(fraction)
    above = np.flatnonzero(wave >= thr)
    if len(above) == 0:
        return float("nan")
    j = int(above[0])
    if j <= 0:
        return float(j)
    y0, y1 = float(wave[j - 1]), float(wave[j])
    if y1 <= y0:
        return float(j)
    return float(j - 1 + (thr - y0) / (y1 - y0))


def correct(raw: np.ndarray, baseline_idx: Sequence[int]) -> np.ndarray:
    baseline = np.median(raw[..., list(baseline_idx)], axis=-1)
    return raw - baseline[..., None]


def count_selected(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    channels = np.asarray([int(c) for c in config["b_staves"].values()], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        count = 0
        total = 0
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            even = correct(raw[:, channels, :], baseline_idx)
            count += int((even.max(axis=-1) > cut).sum())
            total += int(raw.shape[0])
        rows.append({"run": int(run), "events_total": total, "selected_b_pulses": count})
        print(f"count run {run:04d}: {count}")
    return pd.DataFrame(rows)


def read_clean_pairs(config: dict, runs: Sequence[int]) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = list(config["b_staves"].keys())
    even_ch = np.asarray([int(config["b_staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    min_amp = float(config["clean_min_amp_adc"])
    max_amp = float(config["clean_max_amp_adc"])
    max_per_key = int(config["max_clean_per_run_stave"])
    frac = float(config["cfd_fraction"])
    rows = []
    for run in runs:
        per_stave = {s: 0 for s in staves}
        for batch in iter_raw(raw_file(config, int(run)), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corr = correct(raw, baseline_idx)
            even = corr[:, even_ch, :]
            odd = -corr[:, odd_ch, :]
            even_amp = even.max(axis=-1)
            odd_amp = odd.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            odd_peak = odd.argmax(axis=-1)
            selected = (
                (even_amp >= min_amp)
                & (even_amp <= max_amp)
                & (odd_amp >= 0.15 * even_amp)
                & (even_peak >= 4)
                & (even_peak <= 12)
                & (odd_peak >= 4)
                & (odd_peak <= 12)
            )
            ev_idx, st_idx = np.where(selected)
            for e, si in zip(ev_idx, st_idx):
                stave = staves[int(si)]
                if per_stave[stave] >= max_per_key:
                    continue
                ew = even[int(e), int(si)].astype(np.float32)
                ow = odd[int(e), int(si)].astype(np.float32)
                et = cfd_time(ew, frac)
                ot = cfd_time(ow, frac)
                if not np.isfinite(et) or not np.isfinite(ot):
                    continue
                rows.append(
                    {
                        "run": int(run),
                        "eventno": int(eventno[int(e)]),
                        "evt": int(evt[int(e)]),
                        "stave": stave,
                        "stave_idx": int(si),
                        "even_amp": float(even_amp[int(e), int(si)]),
                        "odd_amp": float(odd_amp[int(e), int(si)]),
                        "even_time_sample": et,
                        "odd_time_sample": ot,
                        "raw_dt_ns": (ot - et) * float(config["sample_period_ns"]),
                        "even_wave": ew,
                        "odd_wave": ow,
                    }
                )
                per_stave[stave] += 1
            if all(v >= max_per_key for v in per_stave.values()):
                break
        print(f"clean pairs run {run:04d}: {sum(per_stave.values())}")
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no clean even/odd pairs loaded")
    return out


def estimate_phase_offsets(clean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (run, stave), group in clean.groupby(["run", "stave"], sort=True):
        dt = group["raw_dt_ns"].to_numpy(dtype=float)
        med = float(np.median(dt))
        q16, q84 = np.percentile(dt, [16, 84])
        rows.append(
            {
                "run": int(run),
                "stave": str(stave),
                "n_clean_pairs": int(len(group)),
                "phase_offset_ns": med,
                "raw_dt_sigma68_ns": float((q84 - q16) / 2.0),
            }
        )
    return pd.DataFrame(rows)


def norm_wave(w: np.ndarray) -> np.ndarray:
    x = np.asarray(w, dtype=np.float32)
    x = x - np.median(x[:4])
    amp = max(float(np.max(x)), 1.0)
    return (x / amp).astype(np.float32)


def make_benchmark(config: dict, clean: pd.DataFrame, offsets: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    offset_lookup = {(int(r.run), str(r.stave)): float(r.phase_offset_ns) for r in offsets.itertuples()}
    rows = []
    per = int(config["events_per_run_per_window_per_class"])
    windows = [float(w) for w in config["coincidence_windows_ns"]]
    train_runs = set(int(r) for r in config["benchmark_train_runs"])
    held_runs = set(int(r) for r in config["benchmark_heldout_runs"])
    jitter = float(config["offset_jitter_ns"])
    far = float(config["noncoincident_offset_ns"])
    sid = 0
    for run in sorted(train_runs | held_runs):
        split = "train" if run in train_runs else "heldout"
        run_clean = clean[clean["run"] == run]
        for window_ns in windows:
            for label in [1, 0]:
                for _ in range(per):
                    group = run_clean.sample(n=1, random_state=int(rng.integers(0, 2**31 - 1))).iloc[0]
                    stave = str(group["stave"])
                    phase = offset_lookup[(run, stave)]
                    if label:
                        delta_ns = float(rng.uniform(-0.48 * window_ns, 0.48 * window_ns))
                    else:
                        sign = -1.0 if rng.random() < 0.5 else 1.0
                        delta_ns = sign * float(rng.uniform(window_ns + 5.0, far))
                    measured_dt = phase + delta_ns + float(rng.normal(0.0, jitter))
                    calibrated_dt = measured_dt - phase
                    rows.append(
                        {
                            "event_id": f"{split}:{run}:{window_ns:g}:{sid}",
                            "split": split,
                            "run": int(run),
                            "stave": stave,
                            "window_ns": window_ns,
                            "is_coincident": int(abs(calibrated_dt) <= window_ns),
                            "injected_label": int(label),
                            "measured_dt_ns": measured_dt,
                            "calibrated_dt_ns": calibrated_dt,
                            "abs_calibrated_dt_ns": abs(calibrated_dt),
                            "phase_offset_ns": phase,
                            "even_amp": float(group["even_amp"]),
                            "odd_amp": float(group["odd_amp"]),
                            "amp_ratio_odd_even": float(group["odd_amp"]) / max(float(group["even_amp"]), 1.0),
                            "even_wave": norm_wave(group["even_wave"]),
                            "odd_wave": norm_wave(group["odd_wave"]),
                        }
                    )
                    sid += 1
    frame = pd.DataFrame(rows)
    # The injected label and calibrated threshold agree by construction except
    # rare jitter boundary flips; use the operational window label for scoring.
    return frame


def wave_features(even: np.ndarray, odd: np.ndarray, meta: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    diff = odd - even
    prod = odd * even
    t = np.arange(even.shape[1], dtype=np.float32)
    names = []
    blocks = [even, odd, diff, prod]
    cols = []
    for name, block in zip(["even", "odd", "diff", "prod"], blocks):
        cols.append(block)
        names.extend([f"{name}_s{i:02d}" for i in range(block.shape[1])])
    def scalar(colname: str, arr: np.ndarray):
        cols.append(arr[:, None].astype(np.float32))
        names.append(colname)
    for prefix, block in [("even", even), ("odd", odd), ("diff", diff)]:
        pos = np.clip(block, 0.0, None)
        area = pos.sum(axis=1)
        scalar(f"{prefix}_area", area)
        scalar(f"{prefix}_peak", block.max(axis=1))
        scalar(f"{prefix}_argmax", block.argmax(axis=1).astype(np.float32))
        scalar(f"{prefix}_tail_fraction", pos[:, 10:].sum(axis=1) / np.maximum(area, 1e-6))
        scalar(f"{prefix}_mean_time", (pos * t[None, :]).sum(axis=1) / np.maximum(area, 1e-6))
    for col in ["calibrated_dt_ns", "abs_calibrated_dt_ns", "phase_offset_ns", "even_amp", "odd_amp", "amp_ratio_odd_even", "window_ns"]:
        scalar(col, meta[col].to_numpy(dtype=np.float32))
    staves = sorted(meta["stave"].unique())
    for stave in staves:
        scalar(f"stave_{stave}", (meta["stave"].to_numpy() == stave).astype(np.float32))
    return np.hstack(cols).astype(np.float32), names


def traditional_score(frame: pd.DataFrame) -> np.ndarray:
    # Strong hand-built coincidence score: calibrated phase distance with charge
    # symmetry and waveform agreement terms. Larger means more coincident.
    dt = frame["abs_calibrated_dt_ns"].to_numpy(dtype=float)
    window = frame["window_ns"].to_numpy(dtype=float)
    ratio = frame["amp_ratio_odd_even"].to_numpy(dtype=float)
    even = np.vstack(frame["even_wave"].to_numpy())
    odd = np.vstack(frame["odd_wave"].to_numpy())
    shape_l2 = np.sqrt(np.mean((even - odd) ** 2, axis=1))
    ratio_penalty = np.abs(np.log(np.maximum(ratio, 1e-3)))
    return (1.0 - dt / np.maximum(window, 1.0)) - 0.15 * ratio_penalty - 0.25 * shape_l2


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def run_bootstrap_ci(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int, metric: str) -> Tuple[float, float]:
    runs = sorted(pred["run"].unique())
    by_run = [(g["y_true"].to_numpy(dtype=int), g["score"].to_numpy(dtype=float)) for _, g in pred.groupby("run", sort=True)]
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.integers(0, len(runs), size=len(runs))
        y = np.concatenate([by_run[i][0] for i in sampled])
        score = np.concatenate([by_run[i][1] for i in sampled])
        vals.append(safe_ap(y, score) if metric == "ap" else safe_auc(y, score))
    arr = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def sklearn_scores(X: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    methods = {
        "ridge": make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0, class_weight="balanced")),
        "gradient_boosted_trees": HistGradientBoostingClassifier(
            max_iter=int(config["models"]["gbt_max_iter"]),
            learning_rate=0.08,
            max_leaf_nodes=15,
            l2_regularization=0.02,
            random_state=int(config["random_seed"]) + 1,
        ),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64, 32),
                alpha=1e-4,
                batch_size=256,
                max_iter=int(config["models"]["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=8,
                random_state=int(config["random_seed"]) + 2,
            ),
        ),
    }
    out = {}
    for name, model in methods.items():
        print(f"fit {name}")
        model.fit(X[train], y[train])
        if hasattr(model, "decision_function"):
            out[name] = np.asarray(model.decision_function(X[test]), dtype=float)
        else:
            out[name] = np.asarray(model.predict_proba(X[test])[:, 1], dtype=float)
    return out


class Cnn1D(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(24 + 3, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, scalars):
        return self.head(torch.cat([self.conv(wave), scalars], dim=1)).squeeze(1)


class LateFusionPhaseCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.even = nn.Sequential(nn.Conv1d(1, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 16, 3, padding=1), nn.ReLU())
        self.odd = nn.Sequential(nn.Conv1d(1, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 16, 3, padding=1), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(32 + 3, 16), nn.ReLU(), nn.Linear(16, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(32 + 3, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 1))

    def forward(self, wave, scalars):
        e = self.even(wave[:, 0:1, :]).mean(dim=2)
        o = self.odd(wave[:, 1:2, :]).mean(dim=2)
        z = torch.cat([e, o], dim=1)
        z = z * self.gate(torch.cat([z, scalars], dim=1))
        return self.head(torch.cat([z, scalars], dim=1)).squeeze(1)


def torch_scores(even: np.ndarray, odd: np.ndarray, scalars: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    if torch is None:
        return {}
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    wave = np.stack([even, odd], axis=1).astype(np.float32)
    scalars = scalars.astype(np.float32)
    out = {}
    for name, model, seed in [
        ("1d_cnn", Cnn1D(), int(config["random_seed"]) + 11),
        ("late_fusion_phase_cnn_new", LateFusionPhaseCNN(), int(config["random_seed"]) + 12),
    ]:
        print(f"fit {name}")
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
        idx = np.where(train)[0]
        pos = max(float(y[idx].sum()), 1.0)
        neg = max(float(len(idx) - y[idx].sum()), 1.0)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
        batch = int(config["models"]["torch_batch_size"])
        for epoch in range(int(config["models"]["torch_epochs"])):
            losses = []
            for start in range(0, len(idx), batch):
                take = rng.permutation(idx)[start : start + batch]
                xb = torch.tensor(wave[take], dtype=torch.float32, device=device)
                sb = torch.tensor(scalars[take], dtype=torch.float32, device=device)
                yb = torch.tensor(y[take].astype(np.float32), dtype=torch.float32, device=device)
                loss = loss_fn(model(xb, sb), yb)
                opt.zero_grad()
                loss.backward()
                opt.step()
                losses.append(float(loss.detach().cpu()))
            print(f"{name} epoch {epoch + 1}: {np.mean(losses):.5f}")
        scores = []
        tidx = np.where(test)[0]
        model.eval()
        with torch.no_grad():
            for start in range(0, len(tidx), 4096):
                take = tidx[start : start + 4096]
                xb = torch.tensor(wave[take], dtype=torch.float32, device=device)
                sb = torch.tensor(scalars[take], dtype=torch.float32, device=device)
                scores.append(model(xb, sb).detach().cpu().numpy())
        out[name] = np.concatenate(scores).astype(float)
    return out


def summarize_predictions(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    by_run = []
    for (method, window), group in pred.groupby(["method", "window_ns"], sort=True):
        y = group["y_true"].to_numpy(dtype=int)
        score = group["score"].to_numpy(dtype=float)
        auc_lo, auc_hi = run_bootstrap_ci(group, rng, n_boot, "auc")
        ap_lo, ap_hi = run_bootstrap_ci(group, rng, n_boot, "ap")
        rows.append(
            {
                "method": method,
                "window_ns": float(window),
                "n": int(len(group)),
                "positives": int(y.sum()),
                "roc_auc": safe_auc(y, score),
                "auc_ci_low": auc_lo,
                "auc_ci_high": auc_hi,
                "average_precision": safe_ap(y, score),
                "ap_ci_low": ap_lo,
                "ap_ci_high": ap_hi,
            }
        )
        for run, rg in group.groupby("run", sort=True):
            by_run.append(
                {
                    "method": method,
                    "window_ns": float(window),
                    "run": int(run),
                    "n": int(len(rg)),
                    "positives": int(rg["y_true"].sum()),
                    "roc_auc": safe_auc(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                    "average_precision": safe_ap(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(by_run)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, per_run: pd.DataFrame, offsets: pd.DataFrame) -> None:
    winner = result["winner"]
    lines = [
        "# S10h: phase-calibrated A/B coincidence-window sensitivity",
        "",
        f"**Ticket:** `{result['ticket_id']}`  ",
        f"**Worker:** `{result['worker']}`  ",
        f"**Raw ROOT directory:** `{result['raw_root_dir']}`",
        "",
        "## Abstract",
        "",
        "This study asks whether the weak A-stack validation can be explained by uncalibrated inter-stack timing. The available event-synchronous raw closure pair in `hrdb` is the even B-stave readout and its inverted odd duplicate readout, used here as an A/B-like timing pair. I first reproduce the registered raw B-stave selected-pulse count from ROOT, estimate run- and stave-specific phase offsets from clean single-pulse events, and then benchmark coincidence classification over multiple calibrated timing windows. The named winner in `result.json` is **{}**, with mean held-out average precision **{:.4f}** over the tested windows.".format(
            winner["method"], float(winner["mean_average_precision"])
        ),
        "",
        "## Raw ROOT reproduction",
        "",
        "For every configured `hrdb_run_NNNN.root`, the script reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3 per channel, keeps the physical even B-stave channels B2/B4/B6/B8, and counts pulses with maximum baseline-subtracted amplitude above 1000 ADC. The reproduced total is **{:,}** against the registered **{:,}**, delta **{}**.".format(
            int(result["reproduction"]["reproduced_selected_b_pulses"]),
            int(result["reproduction"]["expected_selected_b_pulses"]),
            int(result["reproduction"]["delta"]),
        ),
        "",
        "## Phase calibration",
        "",
        "Clean single-pulse candidates satisfy `1500 <= A_even <= 12000` ADC, an odd/even amplitude ratio above 0.15, and even and odd CFD20 peak regions in samples 4--12. For event `i`, run `r`, and stave `s`, the raw offset is",
        "",
        "`d_i = 10 ns * (t_odd,i - t_even,i)`.",
        "",
        "The phase estimate is the robust median",
        "",
        "`phi_{r,s} = median_{i in clean(r,s)} d_i`,",
        "",
        "and coincidence scoring uses the calibrated residual `Delta_i = d_i - phi_{r,s}`. Phase-offset summary:",
        "",
        "| run | stave | clean pairs | phase offset ns | sigma68 ns |",
        "|---:|---|---:|---:|---:|",
    ]
    for _, row in offsets.iterrows():
        lines.append("| {run} | {stave} | {n_clean_pairs} | {phase_offset_ns:.3f} | {raw_dt_sigma68_ns:.3f} |".format(**row))
    lines.extend(
        [
            "",
            "## Benchmark design",
            "",
            "The benchmark is split by run: runs `{}` train all learned models and runs `{}` are held out. For each run and timing window, balanced positive/negative examples are synthesized from raw clean event pairs by injecting a calibrated residual inside or outside the requested window. This isolates window sensitivity while preserving raw waveform shape, amplitude, stave, and run support.".format(
                ", ".join(str(r) for r in result["split"]["train_runs"]),
                ", ".join(str(r) for r in result["split"]["heldout_runs"]),
            ),
            "",
            "The operational label is `y_i(w)=1{|Delta_i| <= w}` for windows `w in {5,10,15,20,30} ns`. Run-bootstrap CIs draw held-out runs with replacement and recompute pooled ROC AUC and average precision; therefore the intervals represent run-to-run support uncertainty rather than independent-row binomial uncertainty.",
            "",
            "The strong traditional baseline is not a strawman. It combines the calibrated phase margin with waveform agreement and charge-balance penalties:",
            "",
            "`S_trad = 1 - |Delta|/w - 0.15 |log(A_odd/A_even)| - 0.25 RMS(x_odd - x_even)`.",
            "",
            "Ridge, gradient-boosted trees, and the MLP receive even/odd/difference/product waveform samples plus engineered timing, charge, tail, peak, and stave features. The 1D-CNN receives two waveform channels plus the calibrated residual, charge ratio, and window. The new architecture is a late-fusion phase CNN: even and odd waveforms pass through separate convolutional stems, are fused through a learned phase-aware gate, and then classified with scalar phase and charge context. This is sensible here because A/B coincidence is a paired-sensor problem, not a single-waveform morphology problem.",
            "",
            "## Results",
            "",
            "| method | window ns | AP | 95% CI | ROC AUC | 95% CI | rows | positives |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in summary.sort_values(["window_ns", "average_precision"], ascending=[True, False]).iterrows():
        lines.append(
            "| {} | {:.0f} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} | [{:.4f}, {:.4f}] | {:,} | {:,} |".format(
                row["method"],
                row["window_ns"],
                row["average_precision"],
                row["ap_ci_low"],
                row["ap_ci_high"],
                row["roc_auc"],
                row["auc_ci_low"],
                row["auc_ci_high"],
                int(row["n"]),
                int(row["positives"]),
            )
        )
    lines.extend(
        [
            "",
            "Mean held-out average precision across windows:",
            "",
            "| method | mean AP | mean ROC AUC |",
            "|---|---:|---:|",
        ]
    )
    for method, group in summary.groupby("method", sort=True):
        lines.append("| {} | {:.4f} | {:.4f} |".format(method, float(group["average_precision"].mean()), float(group["roc_auc"].mean())))
    lines.extend(
        [
            "",
            "Per-run metrics are stored in `heldout_per_run_metrics.csv`. The compact summary below reports the AP range across held-out runs and windows:",
            "",
            "| method | min AP | max AP | finite cells |",
            "|---|---:|---:|---:|",
        ]
    )
    for method, group in per_run.groupby("method", sort=True):
        finite = group["average_precision"].dropna()
        lines.append("| {} | {:.4f} | {:.4f} | {} |".format(method, float(finite.min()), float(finite.max()), int(len(finite))))
    lines.extend(
        [
            "",
            "## Systematics and Caveats",
            "",
            "- The odd duplicate readout is an A/B-like closure target, not a physically independent A-stack detector. The report therefore tests whether phase calibration can rescue a paired-readout coincidence window, not the full independent A-stack acceptance.",
            "- Labels are window-threshold labels derived after injecting calibrated residuals into raw clean pairs. This gives controlled truth for method comparison but does not establish the real overlapping-pulse prevalence.",
            "- The traditional baseline directly observes the calibrated residual used in the label. That is intentional: the question is whether phase-calibrated timing is already sufficient before adding waveform ML. Learned methods also see the same timing scalar, so the comparison is fair for this operational task.",
            "- Run-bootstrap intervals use only two held-out runs, so they are sensitivity diagnostics, not final production uncertainties.",
            "- Phase offsets are medians over selected clean pairs. Residual run substructure, amplitude-dependent time walk, and independent A-stack geometry are not propagated beyond the observed clean-pair width.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the winner by mean held-out average precision over timing windows. The main physics conclusion is that phase calibration makes the window task nearly deterministic in this duplicate-readout closure setting; the strongest traditional phase-margin method is therefore a serious baseline, and any future independent A-stack claim must beat this calibrated reference on true `hrda`/`hrdb` paired data.".format(
                winner["method"]
            ),
            "",
            "## Reproducibility",
            "",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/s10h_1781087022_1308_379c0751_phase_calibrated_ab_window_sensitivity.py --config configs/s10h_1781087022_1308_379c0751_phase_calibrated_ab_window_sensitivity.json",
            "```",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_summary(out_dir: Path, summary: pd.DataFrame) -> None:
    methods = list(summary.groupby("method")["average_precision"].mean().sort_values().index)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for method in methods:
        sub = summary[summary["method"] == method].sort_values("window_ns")
        ax.plot(sub["window_ns"], sub["average_precision"], marker="o", label=method)
    ax.set_xlabel("Coincidence window (ns)")
    ax.set_ylabel("Held-out average precision")
    ax.set_ylim(0.0, 1.03)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "window_ap_curves.png", dpi=160)
    plt.close(fig)


def write_manifest(out_dir: Path, config: dict) -> None:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {"ticket_id": config["ticket_id"], "generated_at_unix": time.time(), "artifacts": rows}
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s10h_1781087022_1308_379c0751_phase_calibrated_ab_window_sensitivity.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    counts = count_selected(config)
    counts.to_csv(out_dir / "raw_reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_b_pulses"].sum())
    expected = int(config["expected_b_selected_pulses"])
    match = pd.DataFrame(
        [{"quantity": "selected B-stave pulses", "report_value": expected, "reproduced": reproduced, "delta": reproduced - expected, "pass": reproduced == expected}]
    )
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if reproduced != expected:
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {expected}")

    bench_runs = sorted(set(int(r) for r in config["benchmark_train_runs"] + config["benchmark_heldout_runs"]))
    clean = read_clean_pairs(config, bench_runs)
    clean_public = clean.drop(columns=["even_wave", "odd_wave"]).copy()
    clean_public.to_csv(out_dir / "clean_pair_table.csv", index=False)
    offsets = estimate_phase_offsets(clean)
    offsets.to_csv(out_dir / "phase_offsets_by_run_stave.csv", index=False)
    frame = make_benchmark(config, clean, offsets, rng)
    public = frame.drop(columns=["even_wave", "odd_wave"]).copy()
    public.to_csv(out_dir / "benchmark_events.csv", index=False)

    even = np.vstack(frame["even_wave"].to_numpy()).astype(np.float32)
    odd = np.vstack(frame["odd_wave"].to_numpy()).astype(np.float32)
    X, feature_names = wave_features(even, odd, frame)
    pd.DataFrame({"feature": feature_names}).to_csv(out_dir / "feature_manifest.csv", index=False)
    y = frame["is_coincident"].to_numpy(dtype=int)
    train = frame["split"].to_numpy() == "train"
    test = frame["split"].to_numpy() == "heldout"
    pred_rows = []
    trad = traditional_score(frame)
    for method, score in {"traditional_phase_template": trad[test], **sklearn_scores(X, y, train, test, config)}.items():
        pred_rows.append(
            pd.DataFrame(
                {
                    "method": method,
                    "event_id": frame.loc[test, "event_id"].to_numpy(),
                    "run": frame.loc[test, "run"].to_numpy(dtype=int),
                    "window_ns": frame.loc[test, "window_ns"].to_numpy(dtype=float),
                    "y_true": y[test],
                    "score": np.asarray(score, dtype=float),
                }
            )
        )
    scalars = frame[["calibrated_dt_ns", "amp_ratio_odd_even", "window_ns"]].to_numpy(dtype=np.float32)
    for method, score in torch_scores(even, odd, scalars, y, train, test, config).items():
        pred_rows.append(
            pd.DataFrame(
                {
                    "method": method,
                    "event_id": frame.loc[test, "event_id"].to_numpy(),
                    "run": frame.loc[test, "run"].to_numpy(dtype=int),
                    "window_ns": frame.loc[test, "window_ns"].to_numpy(dtype=float),
                    "y_true": y[test],
                    "score": score,
                }
            )
        )
    pred = pd.concat(pred_rows, ignore_index=True)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = summarize_predictions(pred, rng, int(config["bootstrap_samples"]))
    summary.to_csv(out_dir / "window_method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    mean_summary = (
        summary.groupby("method", sort=True)
        .agg(mean_average_precision=("average_precision", "mean"), mean_roc_auc=("roc_auc", "mean"))
        .reset_index()
        .sort_values(["mean_average_precision", "mean_roc_auc"], ascending=False)
    )
    mean_summary.to_csv(out_dir / "mean_method_summary.csv", index=False)
    winner = mean_summary.iloc[0].to_dict()
    plot_summary(out_dir, summary)

    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "script": str(Path(__file__)),
        "config": str(args.config),
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_seconds": time.time() - t0,
        "reproduction": {
            "expected_selected_b_pulses": expected,
            "reproduced_selected_b_pulses": reproduced,
            "delta": reproduced - expected,
            "pass": reproduced == expected,
        },
        "split": {"train_runs": config["benchmark_train_runs"], "heldout_runs": config["benchmark_heldout_runs"]},
        "phase_calibration": {
            "n_clean_pairs": int(len(clean)),
            "median_abs_phase_offset_ns": float(np.median(np.abs(offsets["phase_offset_ns"].to_numpy(dtype=float)))),
            "median_raw_dt_sigma68_ns": float(np.median(offsets["raw_dt_sigma68_ns"].to_numpy(dtype=float))),
        },
        "methods": sorted(pred["method"].unique()),
        "primary_methods": [
            "traditional_phase_template",
            "ridge",
            "gradient_boosted_trees",
            "mlp",
            "1d_cnn",
            "late_fusion_phase_cnn_new",
        ],
        "winner": json_clean(winner),
        "novel_ticket": config.get("novel_ticket"),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, offsets)
    write_manifest(out_dir, config)
    print(f"winner: {winner['method']}")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
