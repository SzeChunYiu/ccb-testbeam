#!/usr/bin/env python3
"""S41c pile-up-aware PID and energy uncertainty calibration benchmark.

The real HRD ROOT files do not contain particle-truth labels.  This study
therefore uses two train-frozen closure targets: duplicate odd-readout charge
for deposited-energy closure, and duplicate-readout charge-depth quantiles for
weak PID support.  Inputs to all fitted models are even-readout waveforms only.
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

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, confusion_matrix, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for name, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = name
    return out


def heldout_runs(config: dict) -> List[int]:
    out: List[int] = []
    for group in config["heldout_groups"]:
        out.extend(int(v) for v in config["run_groups"][group])
    return sorted(set(out))


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_raw_tables(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    lookup = run_group_lookup(config)
    event_rows: List[pd.DataFrame] = []
    pulse_rows: List[pd.DataFrame] = []
    wave_rows: List[np.ndarray] = []
    count_rows: List[dict] = []
    next_event_id = 0
    for run in configured_runs(config):
        count = {"run": run, "group": lookup[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        count.update({s: 0 for s in staves})
        for batch in iter_batches(raw_path(config, run)):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corr = raw - baseline[..., None]
            even = corr[:, even_ch, :]
            odd = -corr[:, odd_ch, :]
            amp = even.max(axis=-1)
            odd_amp = odd.max(axis=-1)
            charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=-1)
            selected = amp > cut
            has = selected.any(axis=1)
            count["events_total"] += int(len(eventno))
            count["events_with_selected"] += int(has.sum())
            count["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                count[stave] += int(selected[:, i].sum())
            if not has.any():
                continue
            ev_idx = np.flatnonzero(has)
            event_ids = np.arange(next_event_id, next_event_id + len(ev_idx), dtype=np.int64)
            next_event_id += len(ev_idx)
            selected_ev = selected[ev_idx]
            depth = selected_ev.shape[1] - 1 - np.argmax(selected_ev[:, ::-1], axis=1)
            event_id_map = np.full(len(eventno), -1, dtype=np.int64)
            event_id_map[ev_idx] = event_ids
            masked_charge = charge[ev_idx] * selected_ev
            masked_odd_charge = odd_charge[ev_idx] * selected_ev
            masked_amp = amp[ev_idx] * selected_ev
            late_charge = np.clip(even[ev_idx, :, 9:], 0.0, None).sum(axis=(1, 2))
            total_charge = np.maximum(masked_charge.sum(axis=1), 1.0)
            event_rows.append(
                pd.DataFrame(
                    {
                        "event_id": event_ids,
                        "run": run,
                        "group": lookup[run],
                        "eventno": eventno[ev_idx],
                        "evt": evt[ev_idx],
                        "multiplicity": selected_ev.sum(axis=1).astype(np.int16),
                        "pileup_proxy": (selected_ev.sum(axis=1) >= 2).astype(np.int16),
                        "depth_idx": depth.astype(np.int16),
                        "even_total_charge": masked_charge.sum(axis=1),
                        "odd_total_charge": masked_odd_charge.sum(axis=1),
                        "even_max_amp": masked_amp.max(axis=1),
                        "saturated_count": ((masked_amp >= sat) & selected_ev).sum(axis=1).astype(np.int16),
                        "late_fraction": late_charge / total_charge,
                    }
                )
            )
            wave_rows.append((even[ev_idx] * selected_ev[:, :, None]).astype(np.float32))
            event_i, stave_i = np.where(selected)
            pulse_rows.append(
                pd.DataFrame(
                    {
                        "event_id": event_id_map[event_i],
                        "run": run,
                        "stave_idx": stave_i.astype(np.int16),
                        "stave": np.asarray(staves)[stave_i],
                        "even_charge": charge[event_i, stave_i],
                        "odd_charge": odd_charge[event_i, stave_i],
                        "even_amp": amp[event_i, stave_i],
                        "odd_amp": odd_amp[event_i, stave_i],
                    }
                )
            )
        count_rows.append(count)
    return pd.concat(event_rows, ignore_index=True), pd.concat(pulse_rows, ignore_index=True), np.vstack(wave_rows), pd.DataFrame(count_rows)


def range_table(config: dict) -> pd.DataFrame:
    arr = np.loadtxt(config["dedx_table"], dtype=float)
    e = arr[:, 0]
    d = arr[:, 1] * float(config["dedx_to_mev_per_cm"])
    order = np.argsort(e)
    e, d = e[order], d[order]
    inv = 1.0 / np.maximum(d, 1e-12)
    r = np.zeros_like(e)
    r[1:] = np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(e))
    return pd.DataFrame({"energy_mev": e, "dedx_mev_cm": d, "range_cm": r})


def stave_priors(config: dict, rt: pd.DataFrame) -> pd.DataFrame:
    energy = rt["energy_mev"].to_numpy(dtype=float)
    ranges = rt["range_cm"].to_numpy(dtype=float)
    beam_range = float(np.interp(float(config["beam_energy_mev"]), energy, ranges))
    rows = []
    for i, (stave, center) in enumerate(config["stave_centers_cm"].items()):
        front_r = max(beam_range - (float(center) - 0.5 * float(config["stave_thickness_cm"])), 0.0)
        back_r = max(beam_range - (float(center) + 0.5 * float(config["stave_thickness_cm"])), 0.0)
        mid_r = max(beam_range - float(center), 0.0)
        e_front = float(np.interp(front_r, ranges, energy))
        e_back = float(np.interp(back_r, ranges, energy))
        e_mid = float(np.interp(mid_r, ranges, energy))
        rows.append(
            {
                "stave": stave,
                "stave_idx": i,
                "center_cm": float(center),
                "residual_energy_mev": e_mid,
                "dedx_mev_cm": float(np.interp(e_mid, energy, rt["dedx_mev_cm"].to_numpy(dtype=float))),
                "expected_edep_mev": max(e_front - e_back, 1e-6),
            }
        )
    return pd.DataFrame(rows)


def fit_birks(pulses: pd.DataFrame, priors: pd.DataFrame, train_mask: np.ndarray) -> dict:
    p = pulses.loc[train_mask & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)]
    lookup = priors.set_index("stave_idx")
    edep = p["stave_idx"].map(lookup["expected_edep_mev"]).to_numpy(dtype=float)
    dedx = p["stave_idx"].map(lookup["dedx_mev_cm"]).to_numpy(dtype=float)
    q = p["odd_charge"].to_numpy(dtype=float)
    best = None
    for kb in np.linspace(0.0, 0.06, 121):
        denom = edep / (1.0 + kb * dedx)
        alpha = float(np.median(q / np.maximum(denom, 1e-12)))
        pred = alpha * denom
        score = float(np.median(np.abs(np.log(np.maximum(q, 1.0)) - np.log(np.maximum(pred, 1.0)))))
        if best is None or score < best["median_abs_log_charge_error"]:
            best = {"kB_cm_per_MeV": float(kb), "alpha_adc_per_MeV": alpha, "median_abs_log_charge_error": score}
    return best


def charge_to_edep(pulses: pd.DataFrame, priors: pd.DataFrame, birks: dict, col: str) -> np.ndarray:
    lookup = priors.set_index("stave_idx")
    dedx = pulses["stave_idx"].map(lookup["dedx_mev_cm"]).to_numpy(dtype=float)
    q = pulses[col].to_numpy(dtype=float)
    return q * (1.0 + float(birks["kB_cm_per_MeV"]) * dedx) / max(float(birks["alpha_adc_per_MeV"]), 1e-12)


def aggregate_event(pulses: pd.DataFrame, values: np.ndarray, events: pd.DataFrame) -> np.ndarray:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "value": values})
    summed = tmp.groupby("event_id", sort=False)["value"].sum()
    return events["event_id"].map(summed).astype(float).to_numpy()


def event_features(events: pd.DataFrame, wave: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    parts, names = [], []
    for col in ["multiplicity", "pileup_proxy", "depth_idx", "even_total_charge", "even_max_amp", "saturated_count", "late_fraction"]:
        v = events[col].to_numpy(dtype=float)
        if col in {"even_total_charge", "even_max_amp"}:
            v = np.log1p(np.maximum(v, 0.0))
        parts.append(v[:, None])
        names.append(col)
    charge_by_stave = np.clip(wave, 0.0, None).sum(axis=2)
    amp_by_stave = wave.max(axis=2)
    peak_by_stave = wave.argmax(axis=2).astype(float) / float(wave.shape[2] - 1)
    hit_by_stave = (amp_by_stave > 0).astype(float)
    for arr, prefix in [(charge_by_stave, "log_charge"), (amp_by_stave, "log_amp")]:
        parts.append(np.log1p(np.maximum(arr, 0.0)))
        names.extend([f"{prefix}_B{i}" for i in range(arr.shape[1])])
    parts.extend([hit_by_stave, peak_by_stave])
    names.extend([f"hit_B{i}" for i in range(wave.shape[1])])
    names.extend([f"peak_B{i}" for i in range(wave.shape[1])])
    early = np.clip(wave[:, :, :8], 0.0, None).sum(axis=(1, 2)) / np.maximum(charge_by_stave.sum(axis=1), 1.0)
    parts.append(early[:, None])
    names.append("early_fraction")
    return np.hstack(parts), names


def sample_idx(mask: np.ndarray, max_n: int, seed: int) -> np.ndarray:
    idx = np.flatnonzero(mask)
    if len(idx) <= max_n:
        return idx
    return np.random.default_rng(seed).choice(idx, size=max_n, replace=False)


def exp_clip(v: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(np.asarray(v, dtype=float), -20.0, 20.0))


class MLP(nn.Module):
    def __init__(self, n_in: int, n_out: int = 1):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, 48), nn.ReLU(), nn.Linear(48, 24), nn.ReLU(), nn.Linear(24, n_out))

    def forward(self, x):
        return self.net(x)


class EventCNN(nn.Module):
    def __init__(self, n_tab: int, n_out: int = 1):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(4, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 24, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 48), nn.ReLU(), nn.Linear(48, n_out))

    def forward(self, wave, tab):
        return self.head(torch.cat([self.conv(wave).squeeze(-1), tab], dim=1))


class PileupTransformer(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.embed = nn.Linear(18, 24)
        layer = nn.TransformerEncoderLayer(d_model=24, nhead=4, dim_feedforward=48, batch_first=True, dropout=0.05)
        self.enc = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 48), nn.ReLU(), nn.Linear(48, 3))

    def forward(self, wave, tab):
        z = self.enc(self.embed(wave)).mean(dim=1)
        return self.head(torch.cat([z, tab], dim=1))


def torch_fit_tab(x: np.ndarray, target: np.ndarray, train: np.ndarray, config: dict, seed: int) -> Tuple[MLP, StandardScaler]:
    idx = sample_idx(train, int(config["max_torch_train_events"]), seed)
    scaler = StandardScaler().fit(x[idx])
    ds = TensorDataset(torch.from_numpy(scaler.transform(x[idx]).astype(np.float32)), torch.from_numpy(target[idx].astype(np.float32)))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MLP(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=2e-4)
    for _ in range(int(config["torch_epochs"])):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = nn.SmoothL1Loss()(model(xb).squeeze(1), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def torch_pred_tab(model: MLP, scaler: StandardScaler, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    with torch.no_grad():
        for start in range(0, len(xs), 8192):
            out.append(model(torch.from_numpy(xs[start : start + 8192]).to(device)).cpu().numpy().squeeze())
    return np.concatenate(out)


def normalized_wave(wave: np.ndarray) -> np.ndarray:
    scale = np.maximum(np.percentile(np.abs(wave).reshape(len(wave), -1), 95, axis=1), 1.0)
    return (wave / scale[:, None, None]).astype(np.float32)


def torch_fit_wave(model: nn.Module, wave: np.ndarray, x: np.ndarray, target: np.ndarray, train: np.ndarray, config: dict, seed: int, quantile: bool = False) -> Tuple[nn.Module, StandardScaler]:
    idx = sample_idx(train, int(config["max_torch_train_events"]), seed)
    scaler = StandardScaler().fit(x[idx])
    ds = TensorDataset(torch.from_numpy(normalized_wave(wave[idx])), torch.from_numpy(scaler.transform(x[idx]).astype(np.float32)), torch.from_numpy(target[idx].astype(np.float32)))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=9e-4, weight_decay=1e-4)
    qs = torch.tensor([0.05, 0.50, 0.95], dtype=torch.float32, device=device)
    for _ in range(int(config["torch_epochs"])):
        for wb, xb, yb in loader:
            wb, xb, yb = wb.to(device), xb.to(device), yb.to(device)
            opt.zero_grad()
            out = model(wb, xb)
            if quantile:
                err = yb[:, None] - out
                loss = torch.maximum(qs * err, (qs - 1.0) * err).mean()
            else:
                loss = nn.SmoothL1Loss()(out.squeeze(1), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def torch_pred_wave(model: nn.Module, scaler: StandardScaler, wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    with torch.no_grad():
        for start in range(0, len(x), 4096):
            stop = min(start + 4096, len(x))
            out.append(model(torch.from_numpy(normalized_wave(wave[start:stop])).to(device), torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy())
    return np.concatenate(out, axis=0)


def residuals(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return (pred - y) / np.maximum(y, 1e-9)


def res68(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.percentile(np.abs(residuals(y, pred)), 68))


def bootstrap_energy(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, interval: Tuple[np.ndarray, np.ndarray], held: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    idx0 = np.flatnonzero(held)
    blocks = [g.index.to_numpy(dtype=int) for _, g in events.loc[held].groupby("run")]
    vals = {"res68": [], "bias": [], "mae": [], "coverage": []}
    lo, hi = interval
    for _ in range(reps):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=len(blocks))])
        vals["res68"].append(res68(y[idx], pred[idx]))
        vals["bias"].append(float(np.median(residuals(y[idx], pred[idx]))))
        vals["mae"].append(float(mean_absolute_error(y[idx], pred[idx])))
        vals["coverage"].append(float(np.mean((y[idx] >= lo[idx]) & (y[idx] <= hi[idx]))))
    out = {"n": int(len(idx0))}
    for key, arr in vals.items():
        a = np.asarray(arr, dtype=float)
        out[f"{key}_ci95"] = [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    return out


def conformal_interval(y: np.ndarray, pred: np.ndarray, train: np.ndarray, level: float) -> Tuple[np.ndarray, np.ndarray, float]:
    q = float(np.quantile(np.abs(y[train] - pred[train]), level))
    return np.maximum(pred - q, 1e-9), pred + q, q


def pid_labels(events: pd.DataFrame, train: np.ndarray, config: dict) -> Tuple[np.ndarray, dict]:
    coord = np.log1p(np.maximum(events["odd_total_charge"].to_numpy(dtype=float), 0.0)) - 0.42 * events["depth_idx"].to_numpy(dtype=float) - 0.16 * events["pileup_proxy"].to_numpy(dtype=float)
    lo, hi = np.quantile(coord[train], [float(config["pid_quantile_low"]), float(config["pid_quantile_high"])])
    label = np.full(len(events), -1, dtype=int)
    label[coord <= lo] = 0
    label[coord >= hi] = 1
    return label, {"coordinate": "log1p(odd_total_charge)-0.42*depth_idx-0.16*pileup_proxy", "low_threshold": float(lo), "high_threshold": float(hi)}


def pid_boot(events: pd.DataFrame, labels: np.ndarray, score: np.ndarray, held: np.ndarray, reps: int, seed: int) -> dict:
    eval_mask = held & (labels >= 0)
    y = labels[eval_mask]
    s = score[eval_mask]
    blocks = [np.flatnonzero(events.loc[eval_mask, "run"].to_numpy(dtype=int) == r) for r in np.unique(events.loc[eval_mask, "run"].to_numpy(dtype=int))]
    rng = np.random.default_rng(seed)
    aucs, baccs = [], []
    for _ in range(reps):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=len(blocks))])
        if len(np.unique(y[idx])) < 2:
            continue
        aucs.append(float(roc_auc_score(y[idx], s[idx])))
        pred = (s[idx] >= 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(y[idx], pred, labels=[0, 1]).ravel()
        baccs.append(float(0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1))))
    pred_all = (s >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred_all, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)),
        "roc_auc": float(roc_auc_score(y, s)),
        "roc_auc_ci95": [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))],
        "average_precision": float(average_precision_score(y, s)),
        "balanced_accuracy": float(0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1))),
        "balanced_accuracy_ci95": [float(np.percentile(baccs, 2.5)), float(np.percentile(baccs, 97.5))],
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def markdown_table(frame: pd.DataFrame, cols: List[str]) -> str:
    sub = frame[cols].copy()
    for col in sub.columns:
        sub[col] = sub[col].map(lambda v: f"{v:.5g}" if isinstance(v, float) else str(v))
    widths = [max(len(c), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    lines = ["| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |", "| " + " | ".join("---" for _ in sub.columns) + " |"]
    lines += ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join(lines)


def write_report(out_dir: Path, config: dict, result: dict, counts: pd.DataFrame, priors: pd.DataFrame, energy: pd.DataFrame, pid: pd.DataFrame, strata: pd.DataFrame, leakage: pd.DataFrame) -> None:
    w = result["winner"]
    lines = [
        "# S41c: Pile-up-aware PID and energy uncertainty calibration",
        "",
        "## Abstract",
        "",
        f"This study claims ticket `{config['ticket_id']}`.  The raw `h101/HRDv` B-stack ROOT scan reproduces **{result['raw_reproduction']['reproduced_selected_pulses']:,}** selected pulses, exactly matching the S00 count.  A GEANT4/Birks duplicate-readout closure is benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pile-up transformer with quantile heads.  Splits are by run and 95% confidence intervals resample held-out runs.  The winner named in `result.json` is **{w['method']}**, with composite loss {w['composite_loss']:.5f}, energy res68 {w['energy_res68_frac']:.5f}, interval coverage {w['energy_coverage']:.5f}, and weak-label PID ROC AUC {w['pid_roc_auc']:.5f}.",
        "",
        "## Reproduction from raw ROOT",
        "",
        "For event `e`, channel `c`, and sample `s`, the pedestal is `b_ec = median(HRDv_ecs, s in {0,1,2,3})`.  The corrected waveform is `x_ecs = HRDv_ecs - b_ec`.  B2/B4/B6/B8 are physical even channels 0/2/4/6, and a pulse is selected when `max_s x_ecs > 1000 ADC`.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| selected B-stave pulses | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "## Run inventory and pile-up proxy",
        "",
        "Pile-up support is represented by selected-stave multiplicity, a binary multi-stave overlap flag, late charge fraction, saturation count, and per-stave waveform samples.  These are proxies for overlapping pulses because the real HRD files do not contain injected pile-up truth.",
        "",
        markdown_table(counts, ["run", "group", "events_total", "events_with_selected", "selected_pulses"]),
        "",
        "## Energy target and traditional method",
        "",
        "The duplicate odd readout is used only as a closure target.  A range table is formed from the GEANT4 stopping-power file as `R(E)=int_0^E (dE/dx)^(-1)dE`.  With the nominal B-stave centers, a train-run Birks calibration fits",
        "",
        "`Q_i = alpha DeltaE_i / (1 + kB (dE/dx)_i)`.",
        "",
        "The strong traditional energy comparator inverts this expression for even charges and sums selected staves per event.  The traditional PID comparator is a Gaussian likelihood ratio on the even-readout charge-depth-pileup coordinate, with parameters fitted only on train runs.",
        "",
        markdown_table(priors, ["stave", "center_cm", "residual_energy_mev", "dedx_mev_cm", "expected_edep_mev"]),
        "",
        "## Learned models",
        "",
        "All learned methods exclude run number, event identifiers, odd readout charge, and duplicate-readout labels from inputs.  Ridge and gradient-boosted trees use engineered even-readout topology and waveform summaries.  The MLP uses the same tabular matrix.  The 1D-CNN consumes four selected B-stave waveforms plus tabular features.  The new architecture is a pile-up transformer: each selected-stave waveform is embedded as a token, a one-layer self-attention encoder mixes stave tokens, and three quantile heads estimate 5%, 50%, and 95% log-energy.  Its point prediction is the median head and its interval is the direct quantile interval.",
        "",
        "## Metrics",
        "",
        "The primary energy score is `res68 = percentile_68(|(Ehat-Eodd)/Eodd|)`.  Bias is the median fractional residual.  Conformal intervals for non-quantile models use the train-run absolute residual quantile at nominal 90% coverage.  The PID score is ROC AUC on the held-out weak labels.  The composite ranking minimizes `res68 + |coverage-0.90| + (1-AUC_PID)` among methods with both endpoints.",
        "",
        "## Energy benchmark",
        "",
        markdown_table(energy, ["method", "family", "n", "res68_frac", "res68_ci95", "bias_frac", "coverage", "coverage_ci95", "mae_mev"]),
        "",
        "## PID benchmark",
        "",
        markdown_table(pid, ["method", "n", "roc_auc", "roc_auc_ci95", "average_precision", "balanced_accuracy", "balanced_accuracy_ci95", "tn", "fp", "fn", "tp"]),
        "",
        "## Pile-up strata and systematics",
        "",
        markdown_table(strata, ["stratum", "method", "n", "res68_frac", "coverage", "pid_roc_auc"]),
        "",
        "Important systematics are explicit: the MeV scale is conditional on B-stave geometry and duplicate-readout closure; PID is weak-label, not species truth; multi-stave multiplicity is a pile-up proxy and not a resolved two-pulse truth label; saturation can bias both even and odd charge; and bootstrap CIs are run-block intervals, so they quantify run-to-run variation but not all detector-model uncertainty.",
        "",
        "## Leakage checks",
        "",
        markdown_table(leakage, ["check", "value", "pass"]),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.py --config configs/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    print("1/7 raw ROOT scan", flush=True)
    events, pulses, wave, counts = extract_raw_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw reproduction failed: {total} != {expected}")
    valid = (events["odd_total_charge"].to_numpy(dtype=float) > 100.0) & (events["even_total_charge"].to_numpy(dtype=float) > 100.0)
    events = events.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    valid_ids = set(events["event_id"].astype(int).tolist())
    pulses = pulses[pulses["event_id"].isin(valid_ids).to_numpy() & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)].reset_index(drop=True)

    held_runs = heldout_runs(config)
    held = events["run"].isin(held_runs).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(held_runs).to_numpy()

    print("2/7 energy closure target", flush=True)
    rt = range_table(config)
    priors = stave_priors(config, rt)
    birks = fit_birks(pulses, priors, pulse_train)
    y = aggregate_event(pulses, charge_to_edep(pulses, priors, birks, "odd_charge"), events)
    birks_pred = aggregate_event(pulses, charge_to_edep(pulses, priors, birks, "even_charge"), events)
    x, feature_names = event_features(events, wave)
    log_y = np.log(np.maximum(y, 1e-6))

    print("3/7 energy model panel", flush=True)
    idx = sample_idx(train, int(config["max_train_events"]), seed + 1)
    preds: Dict[str, np.ndarray] = {"traditional_template_birks": birks_pred}
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=2.0)).fit(x[idx], log_y[idx])
    preds["ridge"] = exp_clip(ridge.predict(x))
    gbt = GradientBoostingRegressor(n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.75, random_state=seed + 2).fit(x[idx], log_y[idx])
    preds["gradient_boosted_trees"] = exp_clip(gbt.predict(x))
    mlp, mlp_scaler = torch_fit_tab(x, log_y, train, config, seed + 3)
    preds["mlp"] = exp_clip(torch_pred_tab(mlp, mlp_scaler, x))
    cnn, cnn_scaler = torch_fit_wave(EventCNN(x.shape[1], 1), wave, x, log_y, train, config, seed + 4, quantile=False)
    preds["1d_cnn"] = exp_clip(torch_pred_wave(cnn, cnn_scaler, wave, x).squeeze())
    transformer, tr_scaler = torch_fit_wave(PileupTransformer(x.shape[1]), wave, x, log_y, train, config, seed + 5, quantile=True)
    tr_q = torch_pred_wave(transformer, tr_scaler, wave, x)
    preds["pileup_transformer_quantile_new"] = exp_clip(tr_q[:, 1])

    lo_train, hi_train = np.percentile(y[train], [0.1, 99.9])
    preds = {k: np.clip(v, lo_train, hi_train) for k, v in preds.items()}
    intervals: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    q_abs = {}
    for name, pred in preds.items():
        if name == "pileup_transformer_quantile_new":
            intervals[name] = (np.clip(exp_clip(tr_q[:, 0]), lo_train, hi_train), np.clip(exp_clip(tr_q[:, 2]), lo_train, hi_train))
            q_abs[name] = None
        else:
            lo, hi, q = conformal_interval(y, pred, train, float(config["nominal_interval_level"]))
            intervals[name] = (lo, hi)
            q_abs[name] = q

    print("4/7 PID model panel", flush=True)
    labels, pid_info = pid_labels(events, train, config)
    pid_train = train & (labels >= 0)
    pid_scores: Dict[str, np.ndarray] = {}
    coord = np.log1p(np.maximum(events["even_total_charge"].to_numpy(dtype=float), 0.0)) - 0.42 * events["depth_idx"].to_numpy(dtype=float) - 0.16 * events["pileup_proxy"].to_numpy(dtype=float)
    c0, c1 = coord[pid_train & (labels == 0)], coord[pid_train & (labels == 1)]
    mu0, mu1 = float(c0.mean()), float(c1.mean())
    sd0, sd1 = float(c0.std() + 1e-6), float(c1.std() + 1e-6)
    prior1 = float(labels[pid_train].mean())
    ll0 = -0.5 * ((coord - mu0) / sd0) ** 2 - math.log(sd0) + math.log(max(1.0 - prior1, 1e-3))
    ll1 = -0.5 * ((coord - mu1) / sd1) ** 2 - math.log(sd1) + math.log(max(prior1, 1e-3))
    pid_scores["traditional_template_birks"] = 1.0 / (1.0 + np.exp(np.clip(ll0 - ll1, -40.0, 40.0)))
    pid_scores["ridge"] = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500, random_state=seed + 10)).fit(x[pid_train], labels[pid_train]).predict_proba(x)[:, 1]
    pid_scores["gradient_boosted_trees"] = GradientBoostingClassifier(n_estimators=80, max_depth=3, learning_rate=0.05, subsample=0.75, random_state=seed + 11).fit(x[pid_train], labels[pid_train]).predict_proba(x)[:, 1]
    pid_scores["mlp"] = make_pipeline(StandardScaler(), LogisticRegression(C=0.8, max_iter=500, random_state=seed + 12)).fit(np.column_stack([x, preds["mlp"]])[pid_train], labels[pid_train]).predict_proba(np.column_stack([x, preds["mlp"]]))[:, 1]
    pid_scores["1d_cnn"] = make_pipeline(StandardScaler(), LogisticRegression(C=0.8, max_iter=500, random_state=seed + 13)).fit(np.column_stack([x, preds["1d_cnn"]])[pid_train], labels[pid_train]).predict_proba(np.column_stack([x, preds["1d_cnn"]]))[:, 1]
    pid_scores["pileup_transformer_quantile_new"] = make_pipeline(StandardScaler(), LogisticRegression(C=0.8, max_iter=500, random_state=seed + 14)).fit(np.column_stack([x, tr_q])[pid_train], labels[pid_train]).predict_proba(np.column_stack([x, tr_q]))[:, 1]

    print("5/7 metrics", flush=True)
    families = {
        "traditional_template_birks": "traditional_template_likelihood_birks",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "pileup_transformer_quantile_new": "neural_attention_quantile",
    }
    energy_rows = []
    for i, (name, pred) in enumerate(preds.items()):
        boot = bootstrap_energy(events, y, pred, intervals[name], held, int(config["bootstrap_reps"]), seed + 20 + i)
        lo, hi = intervals[name]
        energy_rows.append(
            {
                "method": name,
                "family": families[name],
                "n": boot["n"],
                "res68_frac": res68(y[held], pred[held]),
                "res68_ci95": boot["res68_ci95"],
                "bias_frac": float(np.median(residuals(y[held], pred[held]))),
                "bias_ci95": boot["bias_ci95"],
                "coverage": float(np.mean((y[held] >= lo[held]) & (y[held] <= hi[held]))),
                "coverage_ci95": boot["coverage_ci95"],
                "mae_mev": float(mean_absolute_error(y[held], pred[held])),
                "mae_ci95": boot["mae_ci95"],
                "interval_absolute_halfwidth_mev": q_abs[name],
            }
        )
    energy_df = pd.DataFrame(energy_rows).sort_values("res68_frac")
    pid_df = pd.DataFrame([{**{"method": name}, **pid_boot(events, labels, score, held, int(config["bootstrap_reps"]), seed + 60 + i)} for i, (name, score) in enumerate(pid_scores.items())]).sort_values("roc_auc", ascending=False)
    composite = energy_df.merge(pid_df[["method", "roc_auc"]], on="method")
    composite["composite_loss"] = composite["res68_frac"] + np.abs(composite["coverage"] - float(config["nominal_interval_level"])) + (1.0 - composite["roc_auc"])
    winner = composite.sort_values("composite_loss").iloc[0].to_dict()

    print("6/7 strata", flush=True)
    strata_rows = []
    stratum_methods = list(dict.fromkeys([str(winner["method"]), "traditional_template_birks"]))
    for stratum, mask in [
        ("single_pulse_proxy", held & (events["pileup_proxy"].to_numpy(dtype=int) == 0)),
        ("multi_stave_pileup_proxy", held & (events["pileup_proxy"].to_numpy(dtype=int) == 1)),
        ("unsaturated", held & (events["saturated_count"].to_numpy(dtype=int) == 0)),
        ("saturated", held & (events["saturated_count"].to_numpy(dtype=int) > 0)),
    ]:
        for method in stratum_methods:
            pred = preds[method]
            lo, hi = intervals[method]
            auc = float("nan")
            pm = mask & (labels >= 0)
            if pm.sum() > 5 and len(np.unique(labels[pm])) == 2:
                auc = float(roc_auc_score(labels[pm], pid_scores[method][pm]))
            strata_rows.append({"stratum": stratum, "method": method, "n": int(mask.sum()), "res68_frac": res68(y[mask], pred[mask]) if mask.sum() else float("nan"), "coverage": float(np.mean((y[mask] >= lo[mask]) & (y[mask] <= hi[mask]))) if mask.sum() else float("nan"), "pid_roc_auc": auc})
    strata_df = pd.DataFrame(strata_rows)

    leakage = pd.DataFrame(
        [
            {"check": "raw_reproduction_exact", "value": f"{total} of {expected}", "pass": total == expected},
            {"check": "train_heldout_run_overlap", "value": str(sorted(set(events.loc[train, "run"]).intersection(set(events.loc[held, "run"])))), "pass": set(events.loc[train, "run"]).isdisjoint(set(events.loc[held, "run"]))},
            {"check": "features_exclude_run_event_odd_readout", "value": ",".join(feature_names), "pass": all(bad not in feature_names for bad in ["run", "eventno", "evt", "odd_total_charge"])},
            {"check": "pid_truth_branch_absent", "value": "h101 branches used: EVENTNO,EVT,HRDv; no species/PID truth", "pass": True},
            {"check": "nominal_interval_level", "value": str(config["nominal_interval_level"]), "pass": True},
        ]
    )

    print("7/7 outputs", flush=True)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    priors.to_csv(out_dir / "geant4_stave_priors.csv", index=False)
    energy_df.to_csv(out_dir / "energy_method_metrics.csv", index=False)
    pid_df.to_csv(out_dir / "pid_method_metrics.csv", index=False)
    composite.sort_values("composite_loss").to_csv(out_dir / "composite_method_ranking.csv", index=False)
    strata_df.to_csv(out_dir / "strata_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame([{"quantity": "selected B-stave pulses", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame([birks]).to_csv(out_dir / "birks_fit.csv", index=False)
    input_paths = [raw_path(config, r) for r in configured_runs(config)] + [Path(config["dedx_table"])]
    input_sha = pd.DataFrame([{"path": str(p), "bytes": int(p.stat().st_size), "sha256": sha256_file(p)} for p in input_paths])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "title": config["title"],
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total, "delta": total - expected, "pass": total == expected},
        "train_runs": sorted(int(v) for v in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(v) for v in events.loc[held, "run"].unique()),
        "n_events": int(len(events)),
        "n_pulses": int(len(pulses)),
        "pid_proxy": pid_info,
        "birks_fit": birks,
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "selection_metric": "energy_res68_frac + abs(coverage-0.90) + (1 - weak_label_pid_roc_auc)",
            "composite_loss": float(winner["composite_loss"]),
            "energy_res68_frac": float(winner["res68_frac"]),
            "energy_res68_ci95": winner["res68_ci95"],
            "energy_coverage": float(winner["coverage"]),
            "energy_coverage_ci95": winner["coverage_ci95"],
            "pid_roc_auc": float(winner["roc_auc"]),
            "bias_frac": float(winner["bias_frac"]),
            "mae_mev": float(winner["mae_mev"]),
        },
        "energy_metrics": json.loads(energy_df.to_json(orient="records")),
        "pid_metrics": json.loads(pid_df.to_json(orient="records")),
        "composite_ranking": json.loads(composite.sort_values("composite_loss").to_json(orient="records")),
        "strata_metrics": json.loads(strata_df.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses.  The held-out run-block benchmark winner is {winner['method']} with energy res68={float(winner['res68_frac']):.5f}, coverage={float(winner['coverage']):.5f}, and weak-label PID ROC AUC={float(winner['roc_auc']):.5f}.  The conclusion is a pile-up-aware calibration closure result, not a hidden species-truth PID claim.",
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, result, counts, priors, energy_df, pid_df, strata_df, leakage)
    outputs = ["REPORT.md", "result.json", "input_sha256.csv", "counts_by_run.csv", "reproduction_match_table.csv", "geant4_stave_priors.csv", "birks_fit.csv", "energy_method_metrics.csv", "pid_method_metrics.csv", "composite_method_ranking.csv", "strata_metrics.csv", "leakage_checks.csv"]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.py --config configs/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "uproot": uproot.__version__, "numpy": np.__version__, "pandas": pd.__version__, "torch": torch.__version__},
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE {out_dir} winner={result['winner']['method']} runtime={result['runtime_sec']}s", flush=True)


if __name__ == "__main__":
    main()
