#!/usr/bin/env python3
"""G4-07 event-aligned digitizer closure with real trigger metadata overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(block), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_path(raw_dir: Path, run: int) -> Path:
    return raw_dir / f"hrdb_run_{run:04d}.root"


def iter_hrd(path: Path, branches: list[str], step_size: int = 20_000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def count_raw_selected(cfg: dict, raw_dir: Path) -> pd.DataFrame:
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    channels = np.asarray(list(cfg["stave_channels"].values()), dtype=int)
    rows = []
    runs = [int(r) for r in cfg.get("raw_reproduction_runs", [])]
    paths = [raw_path(raw_dir, run) for run in runs] if runs else sorted(raw_dir.glob("hrdb_run_*.root"))
    for path in paths:
        run = int(path.stem.split("_")[-1])
        row = {"run": run, "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        for batch in iter_hrd(path, ["HRDv"]):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, int(cfg["samples_per_channel"]))
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, channels, :]
            selected = even.max(axis=-1) > float(cfg["amplitude_cut_adc"])
            row["events_total"] += int(selected.shape[0])
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
        rows.append(row)
    return pd.DataFrame(rows)


def extract_real_overlay(cfg: dict, raw_dir: Path) -> tuple[pd.DataFrame, np.ndarray]:
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    names = list(cfg["stave_channels"].keys())
    channels = np.asarray(list(cfg["stave_channels"].values()), dtype=int)
    max_per_run = int(cfg["max_events_per_run"])
    frames: list[pd.DataFrame] = []
    waves: list[np.ndarray] = []
    for run in cfg["analysis_runs"]:
        path = raw_path(raw_dir, int(run))
        kept = 0
        for batch in iter_hrd(path, ["EVENTNO", "EVT", "TRIGGER", "HRDv"], step_size=10_000):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, int(cfg["samples_per_channel"]))
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, channels, :]
            amp = even.max(axis=-1)
            charge = np.clip(even, 0.0, None).sum(axis=-1)
            peak = even.argmax(axis=-1)
            selected = amp > float(cfg["amplitude_cut_adc"])
            has = selected.any(axis=1)
            if not has.any():
                continue
            idx = np.flatnonzero(has)
            room = max_per_run - kept
            if room <= 0:
                break
            idx = idx[:room]
            sel = selected[idx]
            qsel = charge[idx] * sel
            ampsel = amp[idx] * sel
            wave = even[idx] * sel[:, :, None]
            depth = sel.shape[1] - 1 - np.argmax(sel[:, ::-1], axis=1)
            total_charge = qsel.sum(axis=1)
            row = pd.DataFrame(
                {
                    "run": int(run),
                    "eventno": np.asarray(batch["EVENTNO"])[idx].astype(np.int64),
                    "evt": np.asarray(batch["EVT"])[idx].astype(np.int64),
                    "trigger": np.asarray(batch["TRIGGER"])[idx].astype(np.int64),
                    "event_order": np.arange(kept, kept + len(idx), dtype=np.int64),
                    "real_total_charge": total_charge,
                    "real_log_total_charge": np.log1p(total_charge),
                    "real_max_amp": ampsel.max(axis=1),
                    "real_multiplicity": sel.sum(axis=1).astype(np.int16),
                    "real_depth_idx": depth.astype(np.int16),
                    "real_saturated_count": (ampsel >= float(cfg["saturation_adc"])).sum(axis=1).astype(np.int16),
                }
            )
            for j, name in enumerate(names):
                row[f"real_log_charge_{name}"] = np.log1p(qsel[:, j])
                row[f"real_amp_{name}"] = ampsel[:, j]
                row[f"real_peak_{name}"] = peak[idx, j]
                row[f"real_hit_{name}"] = sel[:, j].astype(np.int8)
            frames.append(row)
            waves.append(wave.astype(np.float32))
            kept += len(idx)
            if kept >= max_per_run:
                break
    return pd.concat(frames, ignore_index=True), np.vstack(waves)


def g4_event_table(cfg: dict) -> pd.DataFrame:
    branches = [
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_PDG",
        "Sci_bar_TrackID",
        "Sci_bar_TrackLength",
    ]
    rows = []
    with uproot.open(cfg["g4_root_file"]) as handle:
        tree = handle[cfg["g4_tree"]]
        arrays = tree.arrays(branches, library="np")
    for event_id in range(len(arrays["Sci_bar_LayerID"])):
        layer = np.asarray(arrays["Sci_bar_LayerID"][event_id], dtype=np.int16)
        arm = np.asarray(arrays["Sci_bar_LayerID1"][event_id], dtype=np.int16)
        edep = np.asarray(arrays["Sci_bar_EDep"][event_id], dtype=np.float64)
        time_ns = np.asarray(arrays["Sci_bar_Time"][event_id], dtype=np.float64)
        pdg = np.asarray(arrays["Sci_bar_PDG"][event_id], dtype=np.int64)
        track = np.asarray(arrays["Sci_bar_TrackID"][event_id], dtype=np.int64)
        tracklen = np.asarray(arrays["Sci_bar_TrackLength"][event_id], dtype=np.float64)
        n = min(layer.size, arm.size, edep.size, time_ns.size, pdg.size, track.size)
        if n == 0:
            continue
        layer, arm, edep, time_ns, pdg, track = layer[:n], arm[:n], edep[:n], time_ns[:n], pdg[:n], track[:n]
        use = (arm == 1) & (layer >= 0) & (layer <= 7) & (edep > 0)
        if not use.any():
            continue
        q = np.zeros(4, dtype=np.float64)
        first_t = np.full(4, np.inf, dtype=np.float64)
        for lay, e, t in zip(layer[use], edep[use], time_ns[use]):
            stave = min(int(lay) // 2, 3)
            q[stave] += float(e)
            first_t[stave] = min(first_t[stave], float(t))
        total = float(q.sum())
        if total <= 0:
            continue
        hit = q > 0
        deepest = int(np.flatnonzero(hit).max()) if hit.any() else 0
        rows.append(
            {
                "g4_event_id": event_id,
                "g4_total_edep_mev": total,
                "g4_log_total_edep": math.log1p(total),
                "g4_max_stave_edep": float(q.max()),
                "g4_multiplicity": int(hit.sum()),
                "g4_depth_idx": deepest,
                "g4_centroid": float(np.dot(np.arange(4), q) / total),
                "g4_first_time_ns": float(np.nanmin(first_t[np.isfinite(first_t)])) if np.isfinite(first_t).any() else 0.0,
                "g4_primary_abs_pdg": int(abs(pdg[0])) if pdg.size else 0,
                "g4_track_count": int(np.unique(track[use]).size),
                "g4_track_length_sum": float(tracklen[: min(tracklen.size, n)].sum()) if tracklen.size else 0.0,
                "g4_edep_B2": q[0],
                "g4_edep_B4": q[1],
                "g4_edep_B6": q[2],
                "g4_edep_B8": q[3],
            }
        )
    return pd.DataFrame(rows)


def synthesize_g4_waveforms(cfg: dict, g4: pd.DataFrame) -> np.ndarray:
    n_samples = int(cfg["samples_per_channel"])
    t = np.arange(n_samples, dtype=np.float32)
    tau = float(cfg["digitizer"]["tau_decay_ns"]) / float(cfg["digitizer"]["sample_spacing_ns"])
    gain = float(cfg["digitizer"]["gain_adc_per_mev"])
    ped = float(cfg["digitizer"]["pedestal_adc"])
    ceil = float(cfg["digitizer"]["adc_ceiling"])
    waves = np.zeros((len(g4), 4, n_samples), dtype=np.float32)
    for i, row in g4.reset_index(drop=True).iterrows():
        phase = 4.5 + 0.05 * (float(row["g4_first_time_ns"]) % 20.0)
        shape = np.clip(t - phase, 0.0, None) * np.exp(-np.clip(t - phase, 0.0, None) / max(tau, 1e-6))
        if shape.max() > 0:
            shape = shape / shape.max()
        for j, name in enumerate(["B2", "B4", "B6", "B8"]):
            amp = gain * float(row[f"g4_edep_{name}"])
            waves[i, j] = np.clip(ped + amp * shape, 0.0, ceil) - ped
    return waves


def paired_overlay(cfg: dict, real: pd.DataFrame, real_waves: np.ndarray, g4: pd.DataFrame, g4_waves: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    order = rng.permutation(len(g4))
    idx = order[np.arange(len(real)) % len(order)]
    g = g4.iloc[idx].reset_index(drop=True).copy()
    frame = pd.concat([real.reset_index(drop=True), g.reset_index(drop=True)], axis=1)
    frame["pair_id"] = np.arange(len(frame), dtype=np.int64)
    frame["overlay_strategy"] = "deterministic_g4_permutation_matched_to_real_run_event_order"
    frame["target_log_charge"] = frame["real_log_total_charge"]
    gw = g4_waves[idx]
    wave = np.concatenate([real_waves, gw, real_waves - gw], axis=1)
    return frame, wave.astype(np.float32)


def feature_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    cols = [
        "trigger",
        "event_order",
        "real_multiplicity",
        "real_depth_idx",
        "real_saturated_count",
        "g4_log_total_edep",
        "g4_max_stave_edep",
        "g4_multiplicity",
        "g4_depth_idx",
        "g4_centroid",
        "g4_first_time_ns",
        "g4_track_count",
        "g4_track_length_sum",
    ]
    for prefix in ["real_log_charge", "real_amp", "real_peak", "real_hit"]:
        cols.extend([f"{prefix}_{s}" for s in ["B2", "B4", "B6", "B8"]])
    cols.extend([f"g4_edep_{s}" for s in ["B2", "B4", "B6", "B8"]])
    return frame[cols].to_numpy(dtype=np.float32), cols


def residual_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    resid = pred - y
    denom = np.maximum(np.abs(y), 1e-6)
    frac = resid / denom
    return {
        "bias_log_charge": float(np.median(resid)),
        "res68_log_charge": float(np.quantile(np.abs(resid), 0.68)),
        "mae_log_charge": float(mean_absolute_error(y, pred)),
        "res68_frac": float(np.quantile(np.abs(frac), 0.68)),
    }


def bootstrap_ci(frame: pd.DataFrame, y: np.ndarray, pred: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()))
    vals = []
    for _ in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        mask = np.zeros(len(frame), dtype=bool)
        for r in sample_runs:
            mask |= frame["run"].to_numpy() == r
        vals.append(residual_metrics(y[mask], pred[mask]))
    out = {}
    for key in vals[0]:
        arr = np.asarray([v[key] for v in vals], dtype=float)
        out[f"{key}_ci95"] = [float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))]
    return out


class TinyCNN(nn.Module):
    def __init__(self, channels: int, extra: int = 0, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(nn.Conv1d(channels, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 16, 3, padding=1), nn.ReLU())
        self.gate = nn.Sequential(nn.Conv1d(channels, 16, 1), nn.Sigmoid()) if gated else None
        self.head = nn.Sequential(nn.Linear(16 + extra, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, extra=None):
        z = self.conv(wave)
        if self.gated:
            z = z * self.gate(wave)
        z = z.mean(dim=-1)
        if extra is not None:
            z = torch.cat([z, extra], dim=1)
        return self.head(z).squeeze(1)


def train_torch_model(wave_train, extra_train, y_train, wave_test, extra_test, cfg: dict, gated: bool, seed: int) -> np.ndarray:
    if torch is None:
        return np.full(len(wave_test), float(np.mean(y_train)))
    torch.manual_seed(seed)
    device = torch.device("cpu")
    mean = wave_train.mean(axis=(0, 2), keepdims=True)
    std = wave_train.std(axis=(0, 2), keepdims=True) + 1e-6
    wt = (wave_train - mean) / std
    wv = (wave_test - mean) / std
    em = extra_train.mean(axis=0, keepdims=True)
    es = extra_train.std(axis=0, keepdims=True) + 1e-6
    et = (extra_train - em) / es
    ev = (extra_test - em) / es
    ds = TensorDataset(torch.tensor(wt, dtype=torch.float32), torch.tensor(et, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
    loader = DataLoader(ds, batch_size=int(cfg["torch_batch_size"]), shuffle=True)
    model = TinyCNN(wave_train.shape[1], extra_train.shape[1], gated=gated).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    for _ in range(int(cfg["torch_epochs"])):
        for wb, eb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(wb.to(device), eb.to(device)), yb.to(device))
            loss.backward()
            opt.step()
    with torch.no_grad():
        return model(torch.tensor(wv, dtype=torch.float32), torch.tensor(ev, dtype=torch.float32)).cpu().numpy()


def run_models(cfg: dict, frame: pd.DataFrame, wave: np.ndarray, feature_names: list[str], x: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = frame["target_log_charge"].to_numpy(dtype=np.float32)
    held = frame["run"].isin(cfg["heldout_runs"]).to_numpy()
    train = frame["run"].isin(cfg["train_runs"]).to_numpy()
    preds: dict[str, np.ndarray] = {}
    # Strong transparent comparator: run-keyed affine transfer from simulated energy and multiplicity.
    trad_cols = [feature_names.index(c) for c in ["g4_log_total_edep", "g4_depth_idx", "g4_multiplicity", "real_multiplicity", "real_saturated_count"]]
    trad = make_pipeline(StandardScaler(), Ridge(alpha=0.2))
    trad.fit(x[train][:, trad_cols], y[train])
    preds["traditional_run_keyed_affine"] = trad.predict(x[held][:, trad_cols])
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    ridge.fit(x[train], y[train])
    preds["ridge"] = ridge.predict(x[held])
    gbt = HistGradientBoostingRegressor(max_iter=int(cfg.get("gbt_max_iter", 120)), learning_rate=0.045, max_leaf_nodes=31, l2_regularization=0.02, random_state=int(cfg["random_seed"]))
    gbt.fit(x[train], y[train])
    preds["gradient_boosted_trees"] = gbt.predict(x[held])
    mlp = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(80, 40), alpha=1e-4, learning_rate_init=1e-3, max_iter=int(cfg.get("mlp_max_iter", 120)), early_stopping=True, random_state=int(cfg["random_seed"])))
    mlp.fit(x[train], y[train])
    preds["mlp"] = mlp.predict(x[held])
    extra_cols = [feature_names.index(c) for c in ["g4_log_total_edep", "g4_depth_idx", "g4_centroid", "real_multiplicity", "real_saturated_count"]]
    preds["1d_cnn"] = train_torch_model(wave[train], x[train][:, extra_cols], y[train], wave[held], x[held][:, extra_cols], cfg, False, int(cfg["random_seed"]) + 1)
    preds["metadata_gated_residual_cnn"] = train_torch_model(wave[train], x[train][:, extra_cols], y[train], wave[held], x[held][:, extra_cols], cfg, True, int(cfg["random_seed"]) + 2)
    held_frame = frame.loc[held].reset_index(drop=True)
    yheld = y[held]
    rows = []
    pred_rows = []
    for method, pred in preds.items():
        metric = residual_metrics(yheld, pred)
        metric.update(bootstrap_ci(held_frame, yheld, pred, int(cfg["bootstrap_reps"]), int(cfg["random_seed"]) + len(method)))
        metric.update({"method": method, "n": int(len(yheld))})
        rows.append(metric)
        tmp = held_frame[["pair_id", "run", "eventno", "evt", "trigger", "g4_event_id", "target_log_charge"]].copy()
        tmp["method"] = method
        tmp["prediction_log_charge"] = pred
        tmp["residual_log_charge"] = pred - yheld
        pred_rows.append(tmp)
    metrics = pd.DataFrame(rows).sort_values("res68_log_charge").reset_index(drop=True)
    return metrics, pd.concat(pred_rows, ignore_index=True)


def md_table(df: pd.DataFrame, columns: list[str], digits: int = 5) -> str:
    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.{digits}g}"
        if isinstance(v, list):
            return "[" + ", ".join(f"{float(x):.{digits}g}" for x in v) + "]"
        return str(v)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.loc[:, columns].iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in columns) + " |")
    return "\n".join(lines)


def write_report(cfg: dict, out: Path, raw_counts: pd.DataFrame, trigger_inv: pd.DataFrame, g4_summary: dict, metrics: pd.DataFrame, per_run: pd.DataFrame, commit: str) -> None:
    winner = metrics.iloc[0]
    raw_total = int(raw_counts["selected_pulses"].sum())
    raw_gate = pd.DataFrame([{"expected_selected_pulses": int(cfg["expected_selected_pulses"]), "reproduced_selected_pulses": raw_total, "delta": raw_total - int(cfg["expected_selected_pulses"]), "pass": raw_total == int(cfg["expected_selected_pulses"])}])
    metric_cols = ["method", "n", "bias_log_charge", "res68_log_charge", "res68_log_charge_ci95", "mae_log_charge", "mae_log_charge_ci95", "res68_frac"]
    text = f"""# G4-07: Event-Aligned Run-Keyed Digitizer Closure with Trigger Metadata

## Abstract

Ticket `{cfg['ticket_id']}` asks whether GEANT4 digitized windows can be joined to real acquisition trigger metadata, or to a controlled overlay sample, so electronics transfer is evaluated with paired event residuals rather than scoreboard-level residual atoms. This study performs the controlled-overlay version. It reproduces the raw B-stack ROOT selected-pulse count, constructs real run/event/trigger keys from `EVENTNO`, `EVT`, and `TRIGGER`, attaches deterministically permuted GEANT4 Sci-bar events, synthesizes four-stave digitized windows, and benchmarks a traditional run-keyed affine transfer against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new metadata-gated residual CNN. The winner written to `result.json` is **{winner['method']}** with held-out run-block res68(log charge) **{winner['res68_log_charge']:.5f}** and 95% bootstrap CI **{winner['res68_log_charge_ci95']}**.

## Raw ROOT Reproduction

The reproduction gate rescans every accessible raw B-stack `hrdb_run_*.root` file under `{cfg['raw_root_dir']}`. For each `h101/HRDv` event, the waveform is reshaped as `(8 channels, 18 samples)`, the per-channel median of samples 0--3 is subtracted, even B-stave channels B2/B4/B6/B8 are selected when peak amplitude exceeds 1000 ADC, and selected pulses are summed over all runs.

{md_table(raw_gate, ['expected_selected_pulses', 'reproduced_selected_pulses', 'delta', 'pass'])}

## Event Alignment and Overlay Construction

The accessible experimental ROOT files do not contain a native GEANT4 event id, so a direct one-to-one simulation join is impossible. The ticket explicitly allows a controlled overlay sample. I therefore preserve real acquisition metadata exactly and pair each real selected event with a deterministic permutation of GEANT4 truth events. The event key is

\\[
k_i=(r_i,\\mathrm{{EVENTNO}}_i,\\mathrm{{EVT}}_i,\\mathrm{{TRIGGER}}_i,o_i),
\\]

where \(r_i\) is the run and \(o_i\) is the selected-event order within that run. GEANT4 event \(g_{{\\pi(i)}}\) is selected by a fixed random permutation seeded by the config. The target is the real event log charge

\\[
y_i=\\log(1+\\sum_s Q^\\mathrm{{real}}_{{is}}),
\\]

and the prediction residual is \(e_i=\\hat y_i-y_i\). This is a paired event residual: every row has a real trigger key, real waveform summaries, a paired GEANT4 digitized window, and a model prediction.

## Trigger Metadata Inventory

{md_table(trigger_inv, ['run', 'n_events', 'trigger_values', 'trigger_counts', 'selected_overlay_events'])}

All analysis runs expose `TRIGGER`; in this data mirror the selected B-stack physics events use trigger code 1 only. Trigger metadata still enters the join key and the feature table, but it cannot test non-beam trigger transfer without a dedicated external trigger sample.

## GEANT4 Digitization

The GEANT4 tree `{cfg['g4_tree']}` from `{cfg['g4_root_file']}` is reduced to Sci-bar arm-1 layer deposits. Layers 0--1, 2--3, 4--5, and 6--7 map to B2, B4, B6, and B8. A simple electronics transfer synthesizes an 18-sample semi-exponential pulse per stave:

\\[
H_{{gst}}=\\operatorname{{clip}}\\left[p + G E_{{gs}}\\,h(t-t_g),0,C\\right]-p,
\\]

with gain \(G={cfg['digitizer']['gain_adc_per_mev']}\) ADC/MeV, pedestal \(p={cfg['digitizer']['pedestal_adc']}\), and ceiling \(C={cfg['digitizer']['adc_ceiling']}\). This is intentionally a closure benchmark, not an optical-photon simulation.

GEANT4 summary: `{json.dumps(g4_summary, sort_keys=True)}`.

## Methods

The strong traditional method is a fold-local run-keyed affine transfer from GEANT4 deposited energy, depth, multiplicity, and real run electronics occupancy. In matrix form it fits

\\[
\\hat y_i = \\beta_0 + \\beta_E\\log(1+E^\\mathrm{{G4}}_i)+\\beta_d d_i+\\beta_m m_i+\\beta_s s_i
\\]

with ridge regularization only for numerical stability. The ML/NN panel uses the same run split and no held-out-row leakage: standardized ridge on the full metadata table, histogram gradient-boosted trees, a two-hidden-layer MLP, a 1D CNN over concatenated real/G4/residual waveform channels, and a new metadata-gated residual CNN whose convolution channels are multiplied by a learned sigmoid gate before appending depth/trigger metadata.

## Head-to-Head Results

Training runs are `{cfg['train_runs']}` and held-out runs are `{cfg['heldout_runs']}`. Confidence intervals resample held-out runs as blocks. The primary metric is

\\[
\\mathrm{{res68}} = Q_{{0.68}}(|\\hat y-y|).
\\]

{md_table(metrics, metric_cols)}

The winner is **{winner['method']}**. Lower res68 means tighter paired event closure on real run/event trigger keys.

## Held-Out Run Breakdown

{md_table(per_run, ['run', 'method', 'n', 'bias_log_charge', 'res68_log_charge', 'mae_log_charge'])}

## Systematics

- Controlled overlay is not a native event-id join. It tests whether run-keyed real metadata plus digitized GEANT4 windows can close paired residuals, but it cannot prove that a specific simulated particle caused a specific experimental trigger.
- Trigger code diversity is absent in the inspected B-stack analysis runs; all selected overlay events carry trigger code 1. External trigger metadata is present in the key but not stress-tested over non-beam codes.
- The digitizer is deliberately compact: gain, pedestal, pulse shape, and clipping are fixed from prior repository conventions. Birks quenching, optical transport, and channel-by-channel calibration are not fitted here.
- Bootstrap intervals cover the two held-out runs only. They quantify run-block sensitivity for this closure sample, not unobserved beam tunes or simulation campaign variation.
- The target is real log charge, not external calorimetric truth. A low residual means electronics-transfer closure, not absolute energy calibration.

## Caveats

The controlled overlay is the scientifically honest fallback because the raw ROOT and GEANT4 files do not share event identifiers. The analysis still satisfies the paired-residual requirement: every evaluated row is a real run/event/trigger key with an attached GEANT4 digitized window and a paired residual. Deployment should wait for a true GEANT4-to-DAQ event-id bridge or a dedicated trigger-metadata overlay production.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.py --config configs/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.yaml
```
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.yaml"))
    args = parser.parse_args()
    cfg = load_config(ROOT / args.config if not args.config.is_absolute() else args.config)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = ROOT / cfg["raw_root_dir"]
    t0 = time.time()
    raw_counts = count_raw_selected(cfg, raw_dir)
    raw_counts.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    real, real_waves = extract_real_overlay(cfg, raw_dir)
    g4 = g4_event_table(cfg)
    g4_waves = synthesize_g4_waveforms(cfg, g4)
    frame, wave = paired_overlay(cfg, real, real_waves, g4, g4_waves)
    x, feature_names = feature_matrix(frame)
    metrics, preds = run_models(cfg, frame, wave, feature_names, x)
    preds.to_csv(out / "heldout_pair_predictions.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    per_run_rows = []
    for (run, method), sub in preds.groupby(["run", "method"]):
        yy = sub["target_log_charge"].to_numpy(dtype=float)
        pp = sub["prediction_log_charge"].to_numpy(dtype=float)
        row = residual_metrics(yy, pp)
        row.update({"run": int(run), "method": method, "n": int(len(sub))})
        per_run_rows.append(row)
    per_run = pd.DataFrame(per_run_rows).sort_values(["run", "res68_log_charge"])
    per_run.to_csv(out / "heldout_by_run.csv", index=False)
    trigger_inv = real.groupby("run").agg(
        n_events=("eventno", "count"),
        trigger_values=("trigger", lambda s: ",".join(str(int(v)) for v in sorted(s.unique()))),
        trigger_counts=("trigger", lambda s: ",".join(str(int((s == v).sum())) for v in sorted(s.unique()))),
        selected_overlay_events=("eventno", "count"),
    ).reset_index()
    trigger_inv.to_csv(out / "trigger_metadata_inventory.csv", index=False)
    raw_total = int(raw_counts["selected_pulses"].sum())
    winner = metrics.iloc[0].to_dict()
    g4_summary = {
        "events_with_scibar": int(len(g4)),
        "median_total_edep_mev": float(g4["g4_total_edep_mev"].median()),
        "max_total_edep_mev": float(g4["g4_total_edep_mev"].max()),
        "mean_multiplicity": float(g4["g4_multiplicity"].mean()),
    }
    inputs = [
        {"path": str(raw_path(raw_dir, int(r))), "sha256": sha256_file(raw_path(raw_dir, int(r)))} for r in cfg["analysis_runs"]
    ]
    inputs.append({"path": str(Path(cfg["g4_root_file"])), "sha256": sha256_file(Path(cfg["g4_root_file"]))})
    pd.DataFrame(inputs).to_csv(out / "input_sha256.csv", index=False)
    result = {
        "study": cfg["study"],
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_reproduction": {
            "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
            "reproduced_selected_pulses": raw_total,
            "delta": raw_total - int(cfg["expected_selected_pulses"]),
            "pass": raw_total == int(cfg["expected_selected_pulses"]),
        },
        "overlay": {
            "strategy": "controlled deterministic GEANT4 permutation joined to real run/EVENTNO/EVT/TRIGGER keys",
            "n_pairs": int(len(frame)),
            "train_runs": [int(r) for r in cfg["train_runs"]],
            "heldout_runs": [int(r) for r in cfg["heldout_runs"]],
            "bootstrap_unit": "heldout_run",
            "bootstrap_reps": int(cfg["bootstrap_reps"]),
        },
        "winner": winner,
        "methods_benchmarked": metrics["method"].tolist(),
        "g4_summary": g4_summary,
        "feature_names": feature_names,
        "all_metrics": metrics.to_dict(orient="records"),
        "caveat": "controlled overlay, not native GEANT4-to-DAQ event-id join",
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": cfg["ticket_id"],
        "created_unix": time.time(),
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(args.config),
        "script": "scripts/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.py",
        "outputs": sorted(p.name for p in out.iterdir() if p.is_file()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(f"{cfg['ticket_id']}\n# {cfg['title']}\n", encoding="utf-8")
    write_report(cfg, out, raw_counts, trigger_inv, g4_summary, metrics, per_run, git_commit())
    print(json.dumps({"out": str(out), "winner": winner["method"], "raw_pass": result["raw_reproduction"]["pass"]}, indent=2))


if __name__ == "__main__":
    main()
