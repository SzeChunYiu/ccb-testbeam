#!/usr/bin/env python3
"""S14g: GEANT4-anchored B-stack energy calibration benchmark.

The analysis deliberately uses raw B-stack ROOT as the reproduction gate. The
held-out target is the duplicate odd readout converted to deposited energy with
a train-run Birks calibration anchored by /home/billy/ccb-geant4/dedx_p_in_CD2.txt.
All model inputs use only even readout waveforms and event topology.
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
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - torch is available in the documented env
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


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
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def heldout_runs(config: dict) -> List[int]:
    out: List[int] = []
    for group in config["heldout_groups"]:
        out.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(out))


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_tables(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    group_lookup = group_for_run(config)
    event_frames: List[pd.DataFrame] = []
    pulse_frames: List[pd.DataFrame] = []
    event_waves: List[np.ndarray] = []
    pulse_waves: List[np.ndarray] = []
    counts: List[dict] = []
    next_event_id = 0

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {"run": run, "group": group_lookup[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        count.update({stave: 0 for stave in staves})
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_ch, :]
            odd = corrected[:, odd_ch, :]

            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_amp = (-odd).max(axis=-1)
            odd_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut
            has = selected.any(axis=1)

            count["events_total"] += int(len(eventno))
            count["events_with_selected"] += int(has.sum())
            count["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                count[stave] += int(selected[:, i].sum())
            if not has.any():
                continue

            idx = np.flatnonzero(has)
            selected_block = selected[idx]
            event_ids = np.arange(next_event_id, next_event_id + len(idx), dtype=np.int64)
            next_event_id += len(idx)
            event_id_map = np.full(len(eventno), -1, dtype=np.int64)
            event_id_map[idx] = event_ids
            depth_idx = selected_block.shape[1] - 1 - np.argmax(selected_block[:, ::-1], axis=1)
            even_amp_sel = even_amp[idx] * selected_block
            even_charge_sel = even_charge[idx] * selected_block
            odd_charge_sel = odd_charge[idx] * selected_block
            saturated_sel = (even_amp_sel >= sat) & selected_block

            event_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_ids,
                        "run": run,
                        "group": group_lookup[run],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "multiplicity": selected_block.sum(axis=1).astype(np.int16),
                        "depth_idx": depth_idx.astype(np.int16),
                        "depth_stave": np.asarray(staves)[depth_idx],
                        "even_total_charge": even_charge_sel.sum(axis=1),
                        "odd_total_charge": odd_charge_sel.sum(axis=1),
                        "even_max_amp": even_amp_sel.max(axis=1),
                        "odd_max_amp": (odd_amp[idx] * selected_block).max(axis=1),
                        "saturated_count": saturated_sel.sum(axis=1).astype(np.int16),
                        "any_saturated": saturated_sel.any(axis=1),
                    }
                )
            )
            event_wave = even[idx] * selected_block[:, :, None]
            event_waves.append(event_wave.astype(np.float32))

            event_idx, stave_idx = np.where(selected)
            pulse_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_id_map[event_idx],
                        "run": run,
                        "group": group_lookup[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": np.asarray(staves)[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "even_amp": even_amp[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_charge": even_charge[event_idx, stave_idx],
                        "odd_amp": odd_amp[event_idx, stave_idx],
                        "odd_charge": odd_charge[event_idx, stave_idx],
                        "saturated": (even_amp[event_idx, stave_idx] >= sat),
                    }
                )
            )
            pulse_waves.append(even[event_idx, stave_idx, :].astype(np.float32))
        counts.append(count)

    return (
        pd.concat(event_frames, ignore_index=True),
        pd.concat(pulse_frames, ignore_index=True),
        np.vstack(event_waves),
        np.vstack(pulse_waves),
        pd.DataFrame(counts),
    )


def load_dedx_table(config: dict) -> pd.DataFrame:
    arr = np.loadtxt(config["dedx_table"], dtype=float)
    energy = arr[:, 0]
    dedx = arr[:, 1] * float(config["dedx_to_mev_per_cm"])
    order = np.argsort(energy)
    return pd.DataFrame({"energy_mev": energy[order], "dedx_mev_cm": dedx[order]})


def build_range_table(dedx: pd.DataFrame) -> pd.DataFrame:
    e = dedx["energy_mev"].to_numpy(dtype=float)
    d = dedx["dedx_mev_cm"].to_numpy(dtype=float)
    inv = 1.0 / np.maximum(d, 1e-12)
    ranges = np.zeros_like(e)
    ranges[1:] = np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(e))
    return pd.DataFrame({"energy_mev": e, "range_cm": ranges, "dedx_mev_cm": d})


def invert_range_energy(range_table: pd.DataFrame, ranges_cm: np.ndarray) -> np.ndarray:
    r = range_table["range_cm"].to_numpy(dtype=float)
    e = range_table["energy_mev"].to_numpy(dtype=float)
    return np.interp(np.asarray(ranges_cm, dtype=float), r, e, left=e[0], right=e[-1])


def geant4_stave_priors(config: dict, range_table: pd.DataFrame, geometry: str) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    centers = config["geometry_variants"][geometry]["stave_centers_cm"]
    beam_e = float(config["beam_energy_mev"])
    total_range = float(np.interp(beam_e, range_table["energy_mev"], range_table["range_cm"]))
    thickness = float(config["stave_thickness_cm"])
    rows = []
    for i, stave in enumerate(staves):
        center = float(centers[stave])
        front_residual_range = np.maximum(total_range - (center - 0.5 * thickness), 0.0)
        back_residual_range = np.maximum(total_range - (center + 0.5 * thickness), 0.0)
        e_front = float(invert_range_energy(range_table, np.asarray([front_residual_range]))[0])
        e_back = float(invert_range_energy(range_table, np.asarray([back_residual_range]))[0])
        e_center = float(invert_range_energy(range_table, np.asarray([np.maximum(total_range - center, 0.0)]))[0])
        edep = max(e_front - e_back, 1e-6)
        dedx_center = float(np.interp(e_center, range_table["energy_mev"], range_table["dedx_mev_cm"]))
        rows.append(
            {
                "stave": stave,
                "stave_idx": i,
                "center_cm": center,
                "residual_energy_mev": e_center,
                "dedx_mev_cm": dedx_center,
                "expected_edep_mev": edep,
            }
        )
    return pd.DataFrame(rows)


def fit_birks(pulses: pd.DataFrame, prior: pd.DataFrame, train_mask: np.ndarray, charge_col: str) -> dict:
    p = pulses.loc[train_mask & (pulses[charge_col].to_numpy(dtype=float) > 20.0)].copy()
    lookup = prior.set_index("stave_idx")
    edep = p["stave_idx"].map(lookup["expected_edep_mev"]).to_numpy(dtype=float)
    dedx = p["stave_idx"].map(lookup["dedx_mev_cm"]).to_numpy(dtype=float)
    q = p[charge_col].to_numpy(dtype=float)
    best = None
    for kb in np.linspace(0.0, 0.06, 121):
        denom = edep / (1.0 + kb * dedx)
        alpha = float(np.median(q / np.maximum(denom, 1e-12)))
        pred_q = alpha * denom
        score = float(np.median(np.abs(np.log(np.maximum(q, 1.0)) - np.log(np.maximum(pred_q, 1.0)))))
        if best is None or score < best["median_abs_log_charge_error"]:
            best = {"kB_cm_per_MeV": float(kb), "alpha_adc_per_MeV": alpha, "median_abs_log_charge_error": score}
    assert best is not None
    return best


def charge_to_edep(pulses: pd.DataFrame, prior: pd.DataFrame, birks: dict, charge_col: str) -> np.ndarray:
    lookup = prior.set_index("stave_idx")
    dedx = pulses["stave_idx"].map(lookup["dedx_mev_cm"]).to_numpy(dtype=float)
    q = pulses[charge_col].to_numpy(dtype=float)
    return q * (1.0 + float(birks["kB_cm_per_MeV"]) * dedx) / max(float(birks["alpha_adc_per_MeV"]), 1e-12)


def aggregate_event(pulses: pd.DataFrame, values: np.ndarray, events: pd.DataFrame) -> np.ndarray:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "value": values})
    summed = tmp.groupby("event_id", sort=False)["value"].sum()
    return events["event_id"].map(summed).astype(float).to_numpy()


def event_features(events: pd.DataFrame, event_wave: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    cols = ["multiplicity", "depth_idx", "even_total_charge", "even_max_amp", "saturated_count"]
    parts = []
    names = []
    for col in cols:
        v = events[col].to_numpy(dtype=float)
        if "charge" in col or "amp" in col:
            v = np.log1p(np.maximum(v, 0.0))
        parts.append(v[:, None])
        names.append(col)
    charge_by_stave = np.clip(event_wave, 0.0, None).sum(axis=2)
    amp_by_stave = event_wave.max(axis=2)
    hit_by_stave = (amp_by_stave > 0).astype(float)
    peak_by_stave = event_wave.argmax(axis=2).astype(float) / float(event_wave.shape[2] - 1)
    parts.extend([np.log1p(charge_by_stave), np.log1p(np.maximum(amp_by_stave, 0.0)), hit_by_stave, peak_by_stave])
    for prefix in ["log_charge", "log_amp", "hit", "peak"]:
        names.extend([f"{prefix}_stave_{i}" for i in range(event_wave.shape[1])])
    total = np.maximum(charge_by_stave.sum(axis=1), 1.0)
    early = np.clip(event_wave[:, :, :8], 0.0, None).sum(axis=(1, 2)) / total
    late = np.clip(event_wave[:, :, 9:], 0.0, None).sum(axis=(1, 2)) / total
    parts.extend([early[:, None], late[:, None]])
    names.extend(["early_charge_fraction", "late_charge_fraction"])
    return np.hstack(parts), names


def frac_residual(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return (pred - y) / np.maximum(y, 1e-9)


def res68(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.percentile(np.abs(frac_residual(y, pred)), 68))


def bias(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.median(frac_residual(y, pred)))


def run_block_bootstrap(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, held_mask: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    held_idx = np.flatnonzero(held_mask)
    block_frame = pd.DataFrame({"run": events.iloc[held_idx]["run"].to_numpy(dtype=int), "idx": held_idx})
    blocks = [g["idx"].to_numpy(dtype=int) for _, g in block_frame.groupby("run")]
    vals = {"res68": [], "bias": [], "mae_mev": []}
    for _ in range(reps):
        choice = rng.integers(0, len(blocks), size=len(blocks))
        idx = np.concatenate([blocks[i] for i in choice])
        vals["res68"].append(res68(y[idx], pred[idx]))
        vals["bias"].append(bias(y[idx], pred[idx]))
        vals["mae_mev"].append(float(mean_absolute_error(y[idx], pred[idx])))
    out = {}
    for key, value in vals.items():
        arr = np.asarray(value, dtype=float)
        out[f"{key}_ci95"] = [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]
    return out


def fit_power_law(x_charge: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> LinearRegression:
    good = train_mask & (x_charge > 0) & (y > 0)
    model = LinearRegression()
    model.fit(np.log(x_charge[good])[:, None], np.log(y[good]))
    return model


def apply_power_law(model: LinearRegression, x_charge: np.ndarray) -> np.ndarray:
    return exp_clip(model.predict(np.log(np.maximum(x_charge, 1.0))[:, None]))


def exp_clip(log_values: np.ndarray, lo: float = -20.0, hi: float = 20.0) -> np.ndarray:
    return np.exp(np.clip(np.asarray(log_values, dtype=float), lo, hi))


def sample_train_indices(train_mask: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    idx = np.flatnonzero(train_mask)
    if len(idx) <= max_rows:
        return idx
    rng = np.random.default_rng(seed)
    return rng.choice(idx, size=max_rows, replace=False)


def fit_tabular_models(x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[str, object]:
    idx = sample_train_indices(train_mask, int(config["ml_max_train_events"]), int(config["random_seed"]) + 10)
    target = np.log(np.maximum(y[idx], 1e-6))
    models: Dict[str, object] = {}
    models["ridge"] = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
    models["ridge"].fit(x[idx], target)
    models["gradient_boosted_trees"] = GradientBoostingRegressor(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.75,
        random_state=int(config["random_seed"]) + 20,
    )
    models["gradient_boosted_trees"].fit(x[idx], target)
    return models


class TinyMLP(nn.Module):
    def __init__(self, n_in: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, x):
        return self.net(x).squeeze(1)


def fit_torch_mlp(x: np.ndarray, target: np.ndarray, train_mask: np.ndarray, config: dict, extra_seed: int = 0) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train_mask, int(config["ml_max_train_events"]), int(config["random_seed"]) + 60 + extra_seed)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ys = target[idx].astype(np.float32)
    ds = TensorDataset(torch.from_numpy(xs), torch.from_numpy(ys))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 61 + extra_seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyMLP(x.shape[1], hidden=32).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.2e-3, weight_decay=2e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(max(5, int(config["mlp_max_iter"]))):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_torch_mlp(model: object, scaler: StandardScaler, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(xs), 8192):
        stop = min(start + 8192, len(xs))
        with torch.no_grad():
            out.append(model(torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy())
    return np.concatenate(out)


class SmallCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def fit_cnn(event_wave: np.ndarray, x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train_mask, int(config["cnn_max_train_events"]), int(config["random_seed"]) + 40)
    scaler = StandardScaler().fit(x[idx])
    x_train = scaler.transform(x[idx]).astype(np.float32)
    w = event_wave[idx].astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    w = (w / scale[:, None, None]).astype(np.float32)
    t = np.log(np.maximum(y[idx], 1e-6)).astype(np.float32)
    ds = TensorDataset(torch.from_numpy(w), torch.from_numpy(x_train), torch.from_numpy(t))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 41)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SmallCNN(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=9e-4, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["cnn_epochs"])):
        for wb, xb, yb in loader:
            wb = wb.to(device)
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_cnn(model: object, scaler: StandardScaler, event_wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    pred = []
    xs = scaler.transform(x).astype(np.float32)
    for start in range(0, len(x), 4096):
        stop = min(start + 4096, len(x))
        w = event_wave[start:stop].astype(np.float32)
        scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
        w = (w / scale[:, None, None]).astype(np.float32)
        with torch.no_grad():
            out = model(torch.from_numpy(w).to(device), torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy()
        pred.append(out)
    return exp_clip(np.concatenate(pred))


def fit_residual_mlp(x: np.ndarray, baseline: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict) -> Tuple[object, StandardScaler]:
    xb = np.column_stack([x, np.log(np.maximum(baseline, 1e-6))])
    target = np.log(np.maximum(y, 1e-6)) - np.log(np.maximum(baseline, 1e-6))
    return fit_torch_mlp(xb, target, train_mask, config, extra_seed=100)


def predict_residual_mlp(model: object, scaler: StandardScaler, x: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    xb = np.column_stack([x, np.log(np.maximum(baseline, 1e-6))])
    return baseline * exp_clip(predict_torch_mlp(model, scaler, xb), lo=-8.0, hi=8.0)


def metric_row(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, held_mask: np.ndarray, method: str, family: str, config: dict) -> dict:
    idx = np.flatnonzero(held_mask)
    row = {
        "method": method,
        "family": family,
        "n": int(len(idx)),
        "bias_frac": bias(y[idx], pred[idx]),
        "res68_frac": res68(y[idx], pred[idx]),
        "mae_mev": float(mean_absolute_error(y[idx], pred[idx])),
    }
    row.update(run_block_bootstrap(events, y, pred, held_mask, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
    return row


def clip_to_train_target_range(pred: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(y[train_mask], [0.1, 99.9])
    return np.clip(np.asarray(pred, dtype=float), float(lo), float(hi))


def by_run_rows(events: pd.DataFrame, y: np.ndarray, predictions: Dict[str, np.ndarray], held_mask: np.ndarray) -> pd.DataFrame:
    rows = []
    for run, sub in events.loc[held_mask].groupby("run"):
        idx = sub.index.to_numpy(dtype=int)
        for method, pred in predictions.items():
            rows.append(
                {
                    "run": int(run),
                    "method": method,
                    "n": int(len(idx)),
                    "bias_frac": bias(y[idx], pred[idx]),
                    "res68_frac": res68(y[idx], pred[idx]),
                    "mae_mev": float(mean_absolute_error(y[idx], pred[idx])),
                }
            )
    return pd.DataFrame(rows)


def md_table(frame: pd.DataFrame, columns: List[str]) -> str:
    sub = frame[columns].copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else f"{v:.5g}")
        elif sub[col].dtype.kind in "iu":
            sub[col] = sub[col].map(lambda v: f"{int(v)}")
        else:
            sub[col] = sub[col].astype(str)
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + rows)


def make_report(out_dir: Path, config: dict, result: dict, metrics: pd.DataFrame, prior: pd.DataFrame, byrun: pd.DataFrame, leakage: pd.DataFrame) -> None:
    ranked = metrics.sort_values("res68_frac").copy()
    winner = result["winner"]["method"]
    ci = result["winner"]["res68_ci95"]
    lines = [
        "# S14g: GEANT4-anchored energy calibration from CD2 proton dE/dx",
        "",
        "## Abstract",
        "",
        (
            "This study replaces the prior empirical range-energy anchor with the GEANT4/hibeam_g4 "
            "`dedx_p_in_CD2.txt` proton stopping table and evaluates whether learned even-readout "
            "models improve duplicate-readout energy closure. The raw ROOT reproduction gate passes "
            f"exactly at {result['raw_reproduction']['reproduced_selected_pulses']:,} selected B-stave pulses. "
            f"The held-out winner is **{winner}** with res68={result['winner']['res68_frac']:.5f} "
            f"and run-block bootstrap 95% CI [{ci[0]:.5f}, {ci[1]:.5f}]."
        ),
        "",
        "## Data and Reproduction Gate",
        "",
        "The analysis reads `HRDv`, `EVENTNO`, and `EVT` from raw B-stack `hrdb_run_*.root` files. Baseline is the median of samples 0--3. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "## GEANT4/dE/dx Anchor",
        "",
        "The stopping table is interpreted as kinetic energy in MeV and stopping power in GeV/mm; the latter is converted with \\(10^4\\) to MeV/cm. A numerical range table is formed as",
        "",
        "\\[ R(E)=\\int_0^E \\left(\\frac{dE'}{dx}\\right)^{-1} dE'. \\]",
        "",
        "For a 190 MeV incident proton and geometry variant `center_4cm`, the residual energy at depth \\(z\\) is \\(E(R_{190}-z)\\). The expected deposited energy in a virtual 1 cm stave is \\(E(z-t/2)-E(z+t/2)\\).",
        "",
        md_table(prior, ["stave", "center_cm", "residual_energy_mev", "dedx_mev_cm", "expected_edep_mev"]),
        "",
        "## Birks Calibration",
        "",
        "The traditional GEANT4-anchored model fits train-run duplicate odd charges to",
        "",
        "\\[ Q_i = \\alpha\\,\\frac{\\Delta E_i}{1+k_B (dE/dx)_i}. \\]",
        "",
        "For prediction, even charges are inverted by \\(\\widehat{\\Delta E}_i=Q_i(1+k_B(dE/dx)_i)/\\alpha\\), then summed over selected staves in the event. The old S14-style baseline is a train-run log-linear power law between even total charge and the odd-derived deposited energy target.",
        "",
        "## Model Panel",
        "",
        "All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, tabular MLP, a small 1D-CNN over the four B-stave waveforms, and a physics-residual MLP that predicts a multiplicative correction to the Birks baseline.",
        "",
        "## Metrics",
        "",
        "For held-out events, fractional residuals are \\(r=(\\hat{E}-E_{odd})/E_{odd}\\). The primary score is res68, the 68th percentile of \\(|r|\\). Confidence intervals resample held-out runs with replacement.",
        "",
        "All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.",
        "",
        "## Head-to-Head Results",
        "",
        md_table(ranked, ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "## Per-Run Held-Out Scores",
        "",
        md_table(byrun[byrun["method"].isin([winner, "geant4_birks_lookup", "old_power_law"])], ["run", "method", "n", "bias_frac", "res68_frac", "mae_mev"]),
        "",
        "## Leakage and Systematics Checks",
        "",
        md_table(leakage, ["check", "value", "pass"]),
        "",
        "Dominant systematics are the unknown absolute scintillator thickness, the interpretation of the GEANT4 stopping-power units, the lack of particle-truth labels in real data, possible nonlinearity differences between even and odd electronics, saturation above the ADC ceiling, and the use of duplicate-readout closure rather than an external calorimetric truth. Geometry variants are not re-fit here; the report records the nominal 4 cm center geometry and states that the absolute MeV scale remains conditional on it.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/s14g_0000000003_1_g4energy.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14g_0000000003_1_g4energy.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 raw ROOT reproduction", flush=True)
    events, pulses, event_wave, pulse_wave, counts = extract_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw selected-pulse reproduction failed: got {total}, expected {expected}")

    valid_events = (events["odd_total_charge"].to_numpy(dtype=float) > 100.0) & (events["even_total_charge"].to_numpy(dtype=float) > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    event_wave = event_wave[valid_events]
    valid_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_ids).to_numpy() & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)
    pulse_wave = pulse_wave[pulse_valid]

    held = events["run"].isin(heldout_runs(config)).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(heldout_runs(config)).to_numpy()
    print(f"events={len(events)} pulses={len(pulses)} train_events={int(train.sum())} heldout_events={int(held.sum())}", flush=True)

    print("2/7 GEANT4 range table and Birks fit", flush=True)
    dedx = load_dedx_table(config)
    range_table = build_range_table(dedx)
    prior = geant4_stave_priors(config, range_table, config["nominal_geometry"])
    birks = fit_birks(pulses, prior, pulse_train, "odd_charge")
    target_pulse = charge_to_edep(pulses, prior, birks, "odd_charge")
    birks_even_pulse = charge_to_edep(pulses, prior, birks, "even_charge")
    y = aggregate_event(pulses, target_pulse, events)
    birks_pred = aggregate_event(pulses, birks_even_pulse, events)

    print("3/7 feature construction and traditional baseline", flush=True)
    x, feature_names = event_features(events, event_wave)
    power = fit_power_law(events["even_total_charge"].to_numpy(dtype=float), y, train)
    power_pred = apply_power_law(power, events["even_total_charge"].to_numpy(dtype=float))

    print("4/7 tabular ML models", flush=True)
    models = fit_tabular_models(x, y, train, config)
    predictions: Dict[str, np.ndarray] = {
        "old_power_law": power_pred,
        "geant4_birks_lookup": birks_pred,
    }
    for name, model in models.items():
        predictions[name] = exp_clip(model.predict(x))
    mlp_model, mlp_scaler = fit_torch_mlp(x, np.log(np.maximum(y, 1e-6)), train, config, extra_seed=30)
    predictions["mlp"] = exp_clip(predict_torch_mlp(mlp_model, mlp_scaler, x))

    print("5/7 1D-CNN", flush=True)
    try:
        cnn, cnn_scaler = fit_cnn(event_wave, x, y, train, config)
        predictions["1d_cnn"] = predict_cnn(cnn, cnn_scaler, event_wave, x)
        cnn_status = "trained"
    except Exception as exc:
        predictions["1d_cnn"] = np.full(len(y), np.nan)
        cnn_status = f"failed: {exc}"

    print("6/7 physics-residual MLP", flush=True)
    residual_model, residual_scaler = fit_residual_mlp(x, birks_pred, y, train, config)
    predictions["physics_residual_mlp"] = predict_residual_mlp(residual_model, residual_scaler, x, birks_pred)
    predictions = {name: clip_to_train_target_range(pred, y, train) for name, pred in predictions.items()}

    print("7/7 metrics and outputs", flush=True)
    families = {
        "old_power_law": "traditional_empirical",
        "geant4_birks_lookup": "traditional_geant4_birks",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "physics_residual_mlp": "neural_physics_residual",
    }
    metric_rows = []
    for name, pred in predictions.items():
        if np.isfinite(pred).all():
            metric_rows.append(metric_row(events, y, pred, held, name, families[name], config))
    metrics = pd.DataFrame(metric_rows).sort_values("res68_frac").reset_index(drop=True)
    byrun = by_run_rows(events, y, {k: v for k, v in predictions.items() if np.isfinite(v).all()}, held)
    winner_row = metrics.iloc[0].to_dict()

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": str(sorted(set(events.loc[train, "run"].unique()).intersection(set(events.loc[held, "run"].unique())))),
                "pass": set(events.loc[train, "run"].unique()).isdisjoint(set(events.loc[held, "run"].unique())),
            },
            {
                "check": "raw_reproduction_exact",
                "value": f"{total} of {expected}",
                "pass": total == expected,
            },
            {
                "check": "ml_features_exclude_odd_charge_run_event_id",
                "value": ",".join(feature_names),
                "pass": all(bad not in feature_names for bad in ["odd_total_charge", "run", "eventno", "evt"]),
            },
            {
                "check": "cnn_status",
                "value": cnn_status,
                "pass": cnn_status == "trained",
            },
            {
                "check": "birks_kB_cm_per_MeV",
                "value": f"{birks['kB_cm_per_MeV']:.6g}",
                "pass": True,
            },
        ]
    )

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    prior.to_csv(out_dir / "geant4_stave_priors.csv", index=False)
    range_table.to_csv(out_dir / "geant4_range_table.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    byrun.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame(
        [{"quantity": "S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame([birks]).to_csv(out_dir / "birks_fit.csv", index=False)

    input_paths = [raw_path(config, run) for run in configured_runs(config)] + [Path(config["dedx_table"])]
    input_sha = pd.DataFrame([{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_paths])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_pulse_rows_after_valid_charge_cut": int(len(pulses)),
        "train_runs": sorted(int(x) for x in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[held, "run"].unique()),
        "geant4_anchor": {
            "dedx_table": str(config["dedx_table"]),
            "dedx_second_column_units": config["dedx_second_column_units"],
            "dedx_to_mev_per_cm": float(config["dedx_to_mev_per_cm"]),
            "beam_energy_mev": float(config["beam_energy_mev"]),
            "stave_thickness_cm": float(config["stave_thickness_cm"]),
            "nominal_geometry": config["nominal_geometry"],
            "birks_fit": birks,
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "res68_frac": float(winner_row["res68_frac"]),
            "res68_ci95": winner_row["res68_ci95"],
            "bias_frac": float(winner_row["bias_frac"]),
            "mae_mev": float(winner_row["mae_mev"]),
            "mae_mev_ci95": winner_row["mae_mev_ci95"],
        },
        "all_metrics": json.loads(metrics.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": (
            f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
            f"The GEANT4/Birks traditional lookup achieved res68={float(metrics[metrics.method == 'geant4_birks_lookup'].res68_frac.iloc[0]):.5f}; "
            f"the old empirical power law achieved res68={float(metrics[metrics.method == 'old_power_law'].res68_frac.iloc[0]):.5f}. "
            f"Across the ML/NN panel, the held-out winner is {winner_row['method']} with res68={float(winner_row['res68_frac']):.5f}. "
            "The MeV scale is GEANT4/dE/dx anchored but remains conditional on the assumed B-stave thickness, geometry centers, and duplicate-readout closure target rather than external truth."
        ),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, metrics, prior, byrun, leakage)

    outputs = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "geant4_stave_priors.csv",
        "geant4_range_table.csv",
        "birks_fit.csv",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "leakage_checks.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/s14g_0000000003_1_g4energy.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": subprocess.check_output(
                ["/home/billy/anaconda3/bin/python", "-c", "import sklearn; print(sklearn.__version__)"], text=True
            ).strip(),
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
    }
    manifest["outputs"] = {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={result['winner']['method']}", flush=True)


if __name__ == "__main__":
    main()
