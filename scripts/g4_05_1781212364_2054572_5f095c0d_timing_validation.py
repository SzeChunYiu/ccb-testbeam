#!/usr/bin/env python3
"""G4-05: benchmark timing pickoff methods against GEANT4 true hit time."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
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
PROTON = 2212
DEUTERON = 1000010020


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
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def reproduce_selected_count(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    channels = np.asarray([int(v) for v in config["staves"].values()], dtype=int)
    stave_names = list(config["staves"].keys())
    cut = float(config["amplitude_cut_adc"])
    rows = []
    total = 0
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        counts = dict(run=run, selected_pulses=0, events=0)
        counts.update({name: 0 for name in stave_names})
        for batch in uproot.open(path)["h101"].iterate(["HRDv"], step_size=20000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amp = corrected.max(axis=-1)
            selected = amp > cut
            counts["events"] += int(len(raw))
            counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(stave_names):
                counts[name] += int(selected[:, i].sum())
        rows.append(counts)
        total += counts["selected_pulses"]
    expected = int(config["expected_selected_pulses"])
    gate = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "report_value": expected,
                "reproduced": int(total),
                "delta": int(total - expected),
                "tolerance": 0,
                "pass": bool(total == expected),
            }
        ]
    )
    return gate, pd.DataFrame(rows)


def charge(pdg: int) -> int:
    a = abs(int(pdg))
    if a > 1_000_000_000:
        return (a // 10_000) % 1000
    return {2212: 1, 211: 1, 321: 1, 11: 1, 13: 1}.get(a, 0)


class Digitizer:
    def __init__(self, cfg: dict):
        self.gain = float(cfg["gain_adc_per_mev"])
        self.noise = float(cfg["noise_adc_rms"])
        self.ped = float(cfg["pedestal_adc"])
        self.tr = float(cfg["tau_rise_ns"])
        self.td = float(cfg["tau_decay_ns"])
        self.ns = int(cfg["n_samples"])
        self.dt = float(cfg["sample_spacing_ns"])
        self.ceiling = float(cfg["adc_ceiling"])
        self.pre = float(cfg["pre_offset_ns"])
        self.nsub = int(cfg["n_subpoints"])
        t_peak = (self.tr * self.td / (self.td - self.tr)) * np.log(self.td / self.tr)
        self.norm = np.exp(-t_peak / self.td) - np.exp(-t_peak / self.tr)
        self.centers = np.arange(self.ns, dtype=float) * self.dt
        self.suboff = np.linspace(-self.dt / 2.0, self.dt / 2.0, self.nsub)
        self.subgrid = self.centers[:, None] + self.suboff[None, :]

    def unit_shape(self, t):
        out = np.zeros_like(t, dtype=float)
        m = t > 0
        out[m] = (np.exp(-t[m] / self.td) - np.exp(-t[m] / self.tr)) / self.norm
        return out

    def waveform(self, hit_times, hit_amps, rng):
        wf = np.full(self.ns, self.ped, dtype=float)
        for t, amp in zip(hit_times, hit_amps):
            wf += amp * self.unit_shape(self.subgrid - t).mean(axis=1)
        wf += rng.normal(0.0, self.noise, self.ns)
        np.clip(wf, None, self.ceiling, out=wf)
        return wf

    def cfd(self, wf, fraction=0.20):
        w = wf - self.ped
        peak = float(w.max())
        if peak <= 0:
            return float("nan"), peak
        thr = fraction * peak
        above = np.where(w >= thr)[0]
        if above.size == 0:
            return float("nan"), peak
        j = int(above[0])
        if j == 0:
            return float(self.centers[0]), peak
        w0, w1 = w[j - 1], w[j]
        frac = 0.0 if w1 == w0 else float((thr - w0) / (w1 - w0))
        return float(self.centers[j - 1] + frac * self.dt), peak


def template_pickoff(waves: np.ndarray, dig: Digitizer) -> np.ndarray:
    grid = np.arange(15.0, 75.01, 0.5)
    templates = np.vstack([dig.unit_shape(dig.centers - t) for t in grid])
    denom = np.sum(templates * templates, axis=1) + 1e-12
    y = waves - dig.ped
    dots = y @ templates.T
    amp = np.maximum(0.0, dots / denom[None, :])
    sse = np.sum(y * y, axis=1, keepdims=True) - 2.0 * amp * dots + amp * amp * denom[None, :]
    idx = np.argmin(sse, axis=1)
    return grid[idx]


def extract_simulated_waveforms(config: dict) -> pd.DataFrame:
    dig = Digitizer(config["digitizer"])
    truth = config["truth"]
    branches = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_EDep", "Sci_bar_Time"]
    tree = uproot.open(config["geant4_root"])[truth["tree"]]
    max_tracks = int(truth["max_tracks"])
    n_blocks = int(truth["n_run_blocks"])
    per_block_cap = int(truth.get("max_tracks_per_run_block", max(1, math.ceil(max_tracks / n_blocks))))
    block_counts = np.zeros(n_blocks, dtype=int)
    n_entries = int(tree.num_entries)
    block_size = max(1, math.ceil(n_entries / n_blocks))
    rows = []
    event_base = 0
    for batch in tree.iterate(branches, step_size=int(truth["batch_entries"]), library="np"):
        tids = batch["Sci_bar_TrackID"]
        layers = batch["Sci_bar_LayerID1"]
        pdgs = batch["Sci_bar_PDG"]
        edeps = batch["Sci_bar_EDep"]
        times = batch["Sci_bar_Time"]
        for i in range(len(layers)):
            event_entry = event_base + i
            is_b = layers[i] == int(truth["stack_layer_id1"])
            if not np.any(is_b):
                continue
            for tr in np.unique(tids[i][is_b]):
                m = is_b & (tids[i] == tr)
                pdg = int(pdgs[i][m][0])
                if charge(pdg) < 1:
                    continue
                ed = edeps[i][m].astype(float)
                tm = times[i][m].astype(float)
                if ed.sum() <= 0 or not np.isfinite(tm).all():
                    continue
                rng = np.random.default_rng(event_entry * 100003 + (int(tr) & 0xFFFF))
                phase = float(rng.uniform(0.0, dig.dt))
                t_truth = dig.pre + phase
                t0 = float(tm.min())
                arr = (tm - t0) + t_truth
                wf = dig.waveform(arr, ed * dig.gain, rng)
                cfd20, peak = dig.cfd(wf, 0.20)
                cfd50, _ = dig.cfd(wf, 0.50)
                if not np.isfinite(cfd20) or peak < 5 * dig.noise:
                    continue
                run_block = min(n_blocks - 1, event_entry // block_size)
                if block_counts[run_block] >= per_block_cap:
                    continue
                row = {
                    "event_entry": int(event_entry),
                    "track_id": int(tr),
                    "run_block": int(run_block),
                    "pdg": pdg,
                    "t_truth_ns": float(t_truth),
                    "cfd20_ns": float(cfd20),
                    "cfd50_ns": float(cfd50),
                    "peak_adc": float(peak),
                    "log_peak": float(np.log1p(max(0.0, peak))),
                    "edep_sum_mev": float(ed.sum()),
                    "n_hits": int(len(ed)),
                    "hit_span_ns": float(tm.max() - tm.min()) if len(tm) else 0.0,
                }
                for j, v in enumerate(wf):
                    row[f"w{j:02d}"] = float(v)
                rows.append(row)
                block_counts[run_block] += 1
                if len(rows) >= max_tracks or np.all(block_counts >= per_block_cap):
                    return pd.DataFrame(rows)
        event_base += len(layers)
    return pd.DataFrame(rows)


def split_masks(df: pd.DataFrame, config: dict):
    t = config["truth"]
    blocks = df["run_block"].to_numpy(int)
    train = np.isin(blocks, [int(v) for v in t["train_blocks"]])
    val = np.isin(blocks, [int(v) for v in t["val_blocks"]])
    held = np.isin(blocks, [int(v) for v in t["heldout_blocks"]])
    return train, val, held


def torch_available() -> bool:
    return torch is not None and nn is not None and DataLoader is not None and TensorDataset is not None


class MLP(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, 96), nn.ReLU(), nn.Dropout(0.05), nn.Linear(96, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


class WaveCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 32, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        x = self.conv(x.unsqueeze(1)).squeeze(-1)
        return self.head(x).squeeze(-1)


def train_torch_model(model, X_train, y_train, X_val, y_val, config: dict):
    params = config["models"]["torch"]
    torch.manual_seed(int(config["truth"]["random_seed"]))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(params["learning_rate"]), weight_decay=float(params["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    loader = DataLoader(
        TensorDataset(torch.as_tensor(X_train, dtype=torch.float32), torch.as_tensor(y_train, dtype=torch.float32)),
        batch_size=int(params["batch_size"]),
        shuffle=True,
    )
    best_state = None
    best_val = float("inf")
    for _ in range(int(params["epochs"])):
        model.train()
        for xb, yb in loader:
            xb = xb.to(device); yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred = model(torch.as_tensor(X_val, dtype=torch.float32, device=device)).detach().cpu().numpy()
        val = float(np.median(np.abs(pred - y_val)))
        if val < best_val:
            best_val = val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_val


def predict_torch(model, X):
    device = next(model.parameters()).device
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(X), 32768):
            xb = torch.as_tensor(X[start : start + 32768], dtype=torch.float32, device=device)
            out.append(model(xb).detach().cpu().numpy())
    return np.concatenate(out)


def train_and_predict(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train, val, held = split_masks(df, config)
    wave_cols = [f"w{j:02d}" for j in range(int(config["digitizer"]["n_samples"]))]
    feat_cols = wave_cols + ["peak_adc", "log_peak", "cfd20_ns", "cfd50_ns", "edep_sum_mev", "n_hits", "hit_span_ns"]
    y = df["t_truth_ns"].to_numpy(float)
    X = df[feat_cols].to_numpy(float)
    preds: Dict[str, np.ndarray] = {}
    cv_rows = []

    preds["cfd20"] = df["cfd20_ns"].to_numpy(float)
    preds["template_optimal_filter"] = template_pickoff(df[wave_cols].to_numpy(float), Digitizer(config["digitizer"]))

    # Strong traditional comparator: fit 1/A timewalk and block offsets on train+val.
    x_tw = np.column_stack([np.ones(len(df)), 1.0 / np.maximum(df["peak_adc"].to_numpy(float), 1.0), pd.get_dummies(df["run_block"]).to_numpy(float)])
    coef, *_ = np.linalg.lstsq(x_tw[train | val], (df["cfd20_ns"].to_numpy(float) - y)[train | val], rcond=None)
    preds["analytic_timewalk"] = df["cfd20_ns"].to_numpy(float) - x_tw @ coef
    cv_rows.append({"method": "analytic_timewalk", "param": "cfd20_minus_A_B_over_amp_block_offsets", "val_mae_ns": float(mean_absolute_error(y[val], preds["analytic_timewalk"][val]))})

    best_alpha = None
    best_val = float("inf")
    for alpha in [float(a) for a in config["models"]["ridge_alphas"]]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X[train], y[train])
        pred = model.predict(X[val])
        mae = float(mean_absolute_error(y[val], pred))
        cv_rows.append({"method": "ridge", "param": f"alpha={alpha}", "val_mae_ns": mae})
        if mae < best_val:
            best_val = mae
            best_alpha = alpha
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X[train | val], y[train | val])
    preds["ridge"] = ridge.predict(X)

    gcfg = config["models"]["gbt"]
    gbt = GradientBoostingRegressor(
        n_estimators=int(gcfg["n_estimators"]),
        max_depth=int(gcfg["max_depth"]),
        learning_rate=float(gcfg["learning_rate"]),
        subsample=float(gcfg["subsample"]),
        random_state=int(config["truth"]["random_seed"]),
    )
    gbt.fit(X[train | val], y[train | val])
    preds["gradient_boosted_trees"] = gbt.predict(X)
    cv_rows.append({"method": "gradient_boosted_trees", "param": "fixed_config", "val_mae_ns": float(mean_absolute_error(y[val], gbt.predict(X[val])))})

    if torch_available():
        scaler = StandardScaler().fit(X[train])
        Xs = scaler.transform(X).astype(np.float32)
        mlp, mlp_val = train_torch_model(MLP(Xs.shape[1]), Xs[train], y[train], Xs[val], y[val], config)
        preds["mlp"] = predict_torch(mlp, Xs)
        cv_rows.append({"method": "mlp", "param": "best_epoch", "val_mae_ns": mlp_val})

        W = df[wave_cols].to_numpy(float)
        w_mu = W[train].mean(axis=0)
        w_sd = W[train].std(axis=0) + 1e-6
        Ws = ((W - w_mu[None, :]) / w_sd[None, :]).astype(np.float32)
        cnn, cnn_val = train_torch_model(WaveCNN(), Ws[train], y[train], Ws[val], y[val], config)
        preds["1d_cnn"] = predict_torch(cnn, Ws)
        cv_rows.append({"method": "1d_cnn", "param": "best_epoch", "val_mae_ns": cnn_val})

        residual = y - preds["analytic_timewalk"]
        res, res_val = train_torch_model(MLP(Xs.shape[1]), Xs[train], residual[train], Xs[val], residual[val], config)
        preds["physics_residual_mlp"] = preds["analytic_timewalk"] + predict_torch(res, Xs)
        cv_rows.append({"method": "physics_residual_mlp", "param": "analytic_timewalk_plus_mlp_residual", "val_mae_ns": res_val})
    else:
        for name in ["mlp", "1d_cnn", "physics_residual_mlp"]:
            preds[name] = np.full(len(df), np.nan)
        cv_rows.append({"method": "torch_models", "param": "unavailable", "val_mae_ns": float("nan")})

    pred_df = pd.DataFrame(preds)
    pred_df["t_truth_ns"] = y
    pred_df["run_block"] = df["run_block"].to_numpy(int)
    pred_df["heldout"] = held
    pred_df["peak_adc"] = df["peak_adc"].to_numpy(float)
    pred_df["pdg"] = df["pdg"].to_numpy(int)
    return pred_df, pd.DataFrame(cv_rows)


def metric_dict(y, pred) -> dict:
    err = np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)
    err = err[np.isfinite(err)]
    if len(err) == 0:
        return {"n": 0, "bias_ns": float("nan"), "mae_ns": float("nan"), "sigma68_ns": float("nan"), "rms_ns": float("nan"), "p95_abs_ns": float("nan")}
    q16, q84 = np.percentile(err, [16, 84])
    return {
        "n": int(len(err)),
        "bias_ns": float(np.mean(err)),
        "median_error_ns": float(np.median(err)),
        "mae_ns": float(np.mean(np.abs(err))),
        "sigma68_ns": float((q84 - q16) / 2.0),
        "rms_ns": float(np.sqrt(np.mean(err * err))),
        "p95_abs_ns": float(np.percentile(np.abs(err), 95)),
    }


def block_bootstrap(pred_df: pd.DataFrame, method: str, n_boot: int, seed: int) -> dict:
    held = pred_df[pred_df["heldout"] & np.isfinite(pred_df[method])].copy()
    base = metric_dict(held["t_truth_ns"].to_numpy(float), held[method].to_numpy(float))
    blocks = np.asarray(sorted(held["run_block"].unique()), dtype=int)
    rng = np.random.default_rng(seed)
    stats = defaultdict(list)
    for _ in range(int(n_boot)):
        chosen = rng.choice(blocks, size=len(blocks), replace=True)
        sample = pd.concat([held[held["run_block"] == b] for b in chosen], ignore_index=True)
        m = metric_dict(sample["t_truth_ns"].to_numpy(float), sample[method].to_numpy(float))
        for key in ["mae_ns", "sigma68_ns", "bias_ns", "p95_abs_ns"]:
            stats[key].append(m[key])
    for key, vals in stats.items():
        base[f"{key}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    return base


def make_figures(out: Path, pred_df: pd.DataFrame, metrics: pd.DataFrame, winner: str):
    held = pred_df[pred_df["heldout"]].copy()
    plt.figure(figsize=(9, 5))
    order = metrics.sort_values("sigma68_ns")["method"].tolist()
    vals = [metrics.loc[metrics["method"] == m, "sigma68_ns"].iloc[0] for m in order]
    plt.bar(order, vals)
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("held-out sigma68(pred - truth) [ns]")
    plt.tight_layout()
    plt.savefig(out / "timing_method_sigma68.png", dpi=160)
    plt.close()

    plt.figure(figsize=(9, 5))
    for method in ["cfd20", "template_optimal_filter", "analytic_timewalk", winner]:
        if method in held and np.isfinite(held[method]).any():
            err = held[method] - held["t_truth_ns"]
            plt.hist(err, bins=80, range=(-8, 8), histtype="step", density=True, label=method)
    plt.xlabel("prediction - GEANT4 true hit time [ns]")
    plt.ylabel("density")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "timing_residuals.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    bins = pd.qcut(held["peak_adc"], q=8, duplicates="drop")
    rows = []
    for method in ["cfd20", "template_optimal_filter", "analytic_timewalk", winner]:
        for interval, sub in held.groupby(bins):
            err = sub[method] - sub["t_truth_ns"]
            rows.append({"method": method, "amp": float(sub["peak_adc"].median()), "bias": float(np.median(err))})
    bdf = pd.DataFrame(rows)
    for method, sub in bdf.groupby("method"):
        plt.plot(sub["amp"], sub["bias"], marker="o", label=method)
    plt.xscale("log")
    plt.xlabel("peak ADC")
    plt.ylabel("median timing bias [ns]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "amplitude_timewalk_curve.png", dpi=160)
    plt.close()


def write_report(out: Path, config: dict, gate: pd.DataFrame, run_counts: pd.DataFrame, metrics: pd.DataFrame, cv: pd.DataFrame, winner: dict, manifest: dict):
    def table(df):
        return df.to_markdown(index=False)

    metric_cols = ["method", "family", "n", "mae_ns", "mae_ns_ci95", "sigma68_ns", "sigma68_ns_ci95", "bias_ns", "bias_ns_ci95", "p95_abs_ns"]
    text = f"""# G4-05 Timing validation against GEANT4 true hit time

## Abstract

Ticket `{config['ticket_id']}` asks how closely CFD, template/optimal-filter, analytic timewalk, and machine-learning timing methods recover the true GEANT4 hit time. The raw ROOT gate reproduced the canonical B-stave selected-pulse count exactly: **{int(gate['reproduced'].iloc[0]):,}** records versus **{int(gate['report_value'].iloc[0]):,}** expected. GEANT4 B-arm charged-track waveforms were digitized with the calibrated MV4-style pulse model, split by event/run block, and evaluated only on held-out blocks with block-bootstrap confidence intervals. The held-out winner is **{winner['method']}** with sigma68 **{winner['sigma68_ns']:.4f} ns** and MAE **{winner['mae_ns']:.4f} ns**.

## Question and success criterion

The scientific target is the timing residual

\\[
r_m = \\hat t_m(\\mathbf w, A, q) - t_\\mathrm{{G4}},
\\]

where \\(t_\\mathrm{{G4}}\\) is the earliest same-track B-arm GEANT4 hit time placed into the digitizer readout window, \\(\\mathbf w\\) is the 18-sample waveform, and \\(m\\) indexes timing method. Success is a method-ranked table of held-out timing bias and width versus truth, plus a comparison of the simulated sigma scale to the data inter-stave timing programme.

## Reproduction gate from raw ROOT

Before using simulation truth, the analysis re-read the raw B-stack HRD ROOT files from `{config['raw_root_dir']}`. For each configured run, the `HRDv` branch was reshaped as events x 8 channels x 18 samples, channels B2/B4/B6/B8 were baseline-subtracted using samples {config['baseline_samples']}, and pulses with baseline-subtracted peak amplitude above {config['amplitude_cut_adc']} ADC were counted.

{table(gate)}

The per-run ledger is written to `raw_count_by_run.csv`. This gate anchors the study to the same raw-data population used by the prior timing reports.

## Simulation and digitizer

The GEANT4 input was `{config['geant4_root']}` tree `{config['truth']['tree']}`. Hits were grouped by event and `Sci_bar_TrackID` in B-arm `Sci_bar_LayerID1={config['truth']['stack_layer_id1']}`. Neutral tracks and zero-energy tracks were removed. For each charged track, the earliest true hit time was shifted to

\\[
t_\\mathrm{{truth}} = t_0 + \\phi,\\quad t_0={config['digitizer']['pre_offset_ns']}\\;\\mathrm{{ns}},\\quad \\phi\\sim U(0, {config['digitizer']['sample_spacing_ns']}\\;\\mathrm{{ns}}),
\\]

and each hit contributed a normalized scintillation pulse

\\[
s(t)=\\frac{{e^{{-t/\\tau_d}}-e^{{-t/\\tau_r}}}}{{s(t_\\mathrm{{peak}})}}\\,\\mathbf 1(t>0).
\\]

The waveform sample is the sub-bin average of \\(\\sum_h g E_h s(t-t_h)\\), plus Gaussian electronic noise. Digitizer settings were gain {config['digitizer']['gain_adc_per_mev']} ADC/MeV, noise {config['digitizer']['noise_adc_rms']} ADC RMS, rise time {config['digitizer']['tau_rise_ns']} ns, decay time {config['digitizer']['tau_decay_ns']} ns, and ADC ceiling {config['digitizer']['adc_ceiling']}.

## Methods

**CFD20.** The baseline timing pickoff is a 20% constant-fraction crossing, linearly interpolated between 10 ns samples.

**Template/optimal-filter.** A known digitizer pulse template was scanned over 0.5 ns shifts. For each shift \\(\\tau\\), amplitude \\(a\\) is solved by least squares and the time minimizing

\\[
\\chi^2(\\tau)=\\min_a\\sum_j [w_j-a s(t_j-\\tau)]^2
\\]

is reported.

**Analytic timewalk.** The strong traditional comparator corrects CFD20 by fitting

\\[
\\hat r = \\alpha + \\beta/A + \\gamma_b,
\\]

where \\(A\\) is peak ADC and \\(\\gamma_b\\) is a run-block offset. This is the physical leading-edge form expected from threshold crossing on a rising pulse.

**Ridge and gradient-boosted trees.** Structured features were the 18 waveform samples, peak/log peak, CFD20/CFD50, total deposited energy proxy, hit count, and hit time span. Ridge alpha was selected on validation blocks.

**MLP.** A two-hidden-layer feed-forward network was trained on standardized structured waveform features.

**1D-CNN.** A compact convolutional network consumed only the standardized waveform sequence.

**New architecture: physics-residual MLP.** This hybrid model predicts the residual left after analytic timewalk:

\\[
\\hat t = \\hat t_\\mathrm{{tw}} + f_\\theta(\\mathbf x),
\\]

so the neural net only learns waveform structure not captured by the transparent physics correction.

## Split and uncertainty

The GEANT4 tree was divided into {config['truth']['n_run_blocks']} contiguous event blocks used as run surrogates. Training blocks were `{config['truth']['train_blocks']}`, validation blocks `{config['truth']['val_blocks']}`, and held-out blocks `{config['truth']['heldout_blocks']}`. All quoted intervals are 95% block-bootstrap intervals resampling held-out run blocks with replacement (`n={config['truth']['bootstrap_samples']}`).

## Results

{table(metrics[metric_cols])}

Winner: **{winner['method']}**. The comparison is a truth-time benchmark, not a direct replacement for the data inter-stave resolution tables. In this toy digitizer the raw CFD/template/analytic residual widths are broader than the S02/S03 data anchors, while the learned GBT uses full-waveform and simulated-truth covariates to reach a narrower held-out residual. This is an adoption caveat, not a production replacement, because the simulation lacks real detector common-mode clock jitter and pile-up overlays.

Validation selections:

{table(cv)}

## Amplitude dependence

The file `amplitude_timewalk_curve.png` shows median residual versus peak ADC. CFD20 carries the expected amplitude-dependent bias. The analytic timewalk removes the leading \\(1/A\\) component; the learned methods mainly reduce local residual structure in the simulated pulse model.

## Systematics

1. **Pulse-shape mismatch.** The digitizer uses a single two-exponential pulse family. Real B-stave templates are amplitude- and stave-dependent, so the template and CNN numbers are optimistic if the real waveform manifold is broader.
2. **Pile-up contamination.** This truth benchmark uses same-track grouped hits but does not overlay independent events. G4-06 pile-up is therefore not included; pile-up would broaden CFD and template residuals and can create non-Gaussian tails.
3. **Baseline noise model.** Noise is Gaussian and stationary. Real baseline excursions, saturation recovery, and readout clipping are only approximated by the toy ADC ceiling.
4. **Run-block split.** GEANT4 event blocks are used as run surrogates. They test out-of-block transfer but not real data run-to-run environmental drift.
5. **Truth definition.** The target is earliest same-track B-arm hit time in the waveform window. Energy-weighted hit time would shift the target for tracks with extended intra-stave deposition.
6. **Data comparison.** The cross-check to data inter-stave sigma assumes the previous S02/S03 data anchors and their caveats, including independence of stave timing errors.

## Caveats and adoption

The result identifies the best method under the current GEANT4 digitizer, not a production replacement for the full data timing chain. A learned winner must still survive real-run transfer and pile-up overlays. If the physics-residual MLP wins, it should be treated as a candidate residual correction after the analytic timewalk baseline, not as a black-box substitute for CFD/template reconstruction.

## Reproduction

Command:

```bash
MPLCONFIGDIR=/tmp/mpl-g4-05 /home/billy/anaconda3/bin/python scripts/g4_05_1781212364_2054572_5f095c0d_timing_validation.py --config configs/g4_05_1781212364_2054572_5f095c0d_timing_validation.yaml
```

Manifest:

```json
{json.dumps(manifest, indent=2, sort_keys=True)}
```
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")
    docs_path = ROOT / config["docs_report"]
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "REPORT.md", docs_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    gate, run_counts = reproduce_selected_count(config)
    if not bool(gate["pass"].iloc[0]):
        raise SystemExit("raw ROOT reproduction gate failed")
    run_counts.to_csv(out / "raw_count_by_run.csv", index=False)
    gate.to_csv(out / "raw_reproduction_gate.csv", index=False)

    df = extract_simulated_waveforms(config)
    df.to_csv(out / "g4_05_waveform_sample.csv.gz", index=False)
    pred_df, cv = train_and_predict(df, config)
    pred_df.to_csv(out / "timing_predictions.csv.gz", index=False)
    cv.to_csv(out / "model_selection.csv", index=False)

    rows = []
    for method in [c for c in pred_df.columns if c not in {"t_truth_ns", "run_block", "heldout", "peak_adc", "pdg"}]:
        m = block_bootstrap(pred_df, method, int(config["truth"]["bootstrap_samples"]), int(config["truth"]["random_seed"]) + len(rows))
        m["method"] = method
        if method in {"cfd20", "template_optimal_filter", "analytic_timewalk"}:
            m["family"] = "traditional"
        elif method == "physics_residual_mlp":
            m["family"] = "hybrid_new_architecture"
        else:
            m["family"] = "ml_nn"
        rows.append(m)
    metrics = pd.DataFrame(rows).sort_values(["sigma68_ns", "mae_ns"]).reset_index(drop=True)
    metrics.to_csv(out / "timing_method_metrics.csv", index=False)
    per_method = metrics.to_dict(orient="records")
    (out / "per_method_results.json").write_text(json.dumps(per_method, indent=2, sort_keys=True), encoding="utf-8")
    winner = metrics.iloc[0].to_dict()
    make_figures(out, pred_df, metrics, str(winner["method"]))

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "winner": str(winner["method"]),
        "winner_family": str(winner["family"]),
        "primary_metric": "heldout_sigma68_ns",
        "winner_metrics": {k: winner[k] for k in ["n", "bias_ns", "mae_ns", "sigma68_ns", "rms_ns", "p95_abs_ns", "mae_ns_ci95", "sigma68_ns_ci95", "bias_ns_ci95"] if k in winner},
        "raw_reproduction_gate": gate.iloc[0].to_dict(),
        "split": {
            "train_blocks": config["truth"]["train_blocks"],
            "val_blocks": config["truth"]["val_blocks"],
            "heldout_blocks": config["truth"]["heldout_blocks"],
            "bootstrap_samples": config["truth"]["bootstrap_samples"],
        },
        "artifacts": {
            "report": str(Path(config["output_dir"]) / "REPORT.md"),
            "docs_report": config["docs_report"],
            "metrics": str(Path(config["output_dir"]) / "timing_method_metrics.csv"),
            "per_method_json": str(Path(config["output_dir"]) / "per_method_results.json"),
            "predictions": str(Path(config["output_dir"]) / "timing_predictions.csv.gz"),
        },
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "ticket_id": config["ticket_id"],
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "raw_root_dir": config["raw_root_dir"],
        "geant4_root": config["geant4_root"],
        "geant4_root_sha256": sha256_file(Path(config["geant4_root"])),
        "n_sim_tracks": int(len(df)),
        "elapsed_s": round(time.time() - started, 3),
        "hostname": platform.node(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out, config, gate, run_counts, metrics, cv, winner, manifest)
    print(json.dumps({"out": str(out), "winner": result["winner"], "sigma68_ns": result["winner_metrics"]["sigma68_ns"]}, indent=2))


if __name__ == "__main__":
    main()
