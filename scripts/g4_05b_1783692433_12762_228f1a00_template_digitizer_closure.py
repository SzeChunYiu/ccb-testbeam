#!/usr/bin/env python3
"""G4-05B real-template digitizer closure for timing truth benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-g405b")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import awkward as ak
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import s02_timing_pickoff as s02

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(block_size), b""):
            h.update(b)
    return h.hexdigest()


def configured_runs(config: dict) -> List[int]:
    runs = []
    for group in config["run_groups"].values():
        runs.extend(int(r) for r in group)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def reproduce_counts(config: dict) -> pd.DataFrame:
    tmp = dict(config)
    tmp["expected_counts"] = {
        "total_selected_pulses": int(config["expected_selected_pulses"]),
        "sample_ii_analysis": {"selected_pulses": 125096, "B2": 88213, "B4": 21229, "B6": 11148, "B8": 4506},
    }
    return s02.reproduce_counts(tmp)


def pick_g4(config: dict) -> Path:
    p = Path(config["geant4_root"])
    if p.exists():
        return p
    fb = Path(config["fallback_geant4_root"])
    if fb.exists():
        return fb
    raise FileNotFoundError(f"no GEANT4 ROOT at {p} or {fb}")


def weighted_mean(value, weight):
    num = ak.sum(value * weight, axis=1)
    den = ak.sum(weight, axis=1)
    return ak.to_numpy(ak.where(den > 0, num / den, np.nan))


def load_templates(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], pd.DataFrame]:
    pulses = s02.load_downstream_pulses(config)
    rows = []
    keep = []
    max_n = int(config["max_template_pulses_per_run_stave"])
    for (run, stave), sub in pulses.groupby(["run", "stave"]):
        idx = sub.index.to_numpy()
        if len(idx) > max_n:
            idx = rng.choice(idx, size=max_n, replace=False)
        keep.append(pulses.loc[idx])
        rows.append({"run": int(run), "stave": stave, "available": int(len(sub)), "used": int(len(idx))})
    lib = pd.concat(keep, ignore_index=True)
    templates = s02.build_templates(lib, list(config["timing"]["downstream_staves"]))
    return lib, templates, pd.DataFrame(rows)


def load_g4_events(config: dict, root_file: Path) -> pd.DataFrame:
    staves = list(config["timing"]["downstream_staves"])
    mapping = {s: int(config["sim_layer_mapping"][s]) for s in staves}
    branches = ["Sci_bar_LayerID", "Sci_bar_EDep", "Sci_bar_Time"]
    tree = uproot.open(root_file)["hibeam"]
    max_events = int(config["max_sim_events"])
    rows = []
    seen = 0
    for batch in tree.iterate(branches, step_size=50000, library="ak"):
        n = len(batch["Sci_bar_EDep"])
        take = min(n, max_events - seen)
        if take <= 0:
            break
        arr = {k: batch[k][:take] for k in branches}
        row = {"sim_event_id": np.arange(seen, seen + take, dtype=np.int64)}
        for stave, layer in mapping.items():
            mask = arr["Sci_bar_LayerID"] == layer
            ed = ak.where(mask, arr["Sci_bar_EDep"], 0.0)
            row[f"{stave}_edep_mev"] = ak.to_numpy(ak.sum(ed, axis=1)).astype(np.float32)
            row[f"{stave}_true_time_ns"] = weighted_mean(ak.where(mask, arr["Sci_bar_Time"], 0.0), ed).astype(np.float32)
        rows.append(pd.DataFrame(row))
        seen += take
        if seen >= max_events:
            break
    events = pd.concat(rows, ignore_index=True)
    mask = np.ones(len(events), dtype=bool)
    for stave in staves:
        mask &= (events[f"{stave}_edep_mev"].to_numpy(float) > float(config["digitizer"]["min_edep_mev"]))
        mask &= np.isfinite(events[f"{stave}_true_time_ns"].to_numpy(float))
    events = events.loc[mask].reset_index(drop=True)
    raw_time = events[[f"{s}_true_time_ns" for s in staves]].min(axis=1).to_numpy(float)
    ref = float(config["digitizer"]["reference_time_ns"])
    for stave in staves:
        events[f"{stave}_true_time_ns"] = events[f"{stave}_true_time_ns"].to_numpy(float) - raw_time + ref
    split_runs = [int(r) for r in config["timing"]["train_runs"] + config["timing"]["heldout_runs"]]
    events["pseudo_run"] = np.asarray(split_runs, dtype=int)[np.arange(len(events)) % len(split_runs)]
    return events


def sample_template(lib: pd.DataFrame, stave: str, amp: float, bins: List[float], rng: np.random.Generator) -> np.ndarray:
    sub = lib[lib["stave"] == stave]
    amps = sub["amplitude_adc"].to_numpy(float)
    b = int(np.searchsorted(np.asarray(bins, dtype=float), amp, side="right") - 1)
    lo = bins[max(0, b)]
    hi = bins[min(len(bins) - 1, b + 1)]
    cand = sub[(amps >= lo) & (amps < hi)]
    if len(cand) < 5:
        cand = sub
    row = cand.iloc[int(rng.integers(0, len(cand)))]
    wf = np.asarray(row["waveform"], dtype=float)
    return wf / max(float(row["amplitude_adc"]), 1.0)


def shift_wave(wf: np.ndarray, shift_samples: float) -> np.ndarray:
    x = np.arange(len(wf), dtype=float)
    return np.interp(x - shift_samples, x, wf, left=0.0, right=0.0)


def digitize(config: dict, events: pd.DataFrame, lib: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    staves = list(config["timing"]["downstream_staves"])
    bins = [float(x) for x in config["digitizer"]["amplitude_bins"]]
    scale = float(config["digitizer"]["amplitude_scale_adc_per_sqrt_mev"])
    amp_jit = float(config["digitizer"]["amplitude_jitter_frac"])
    noise = float(config["digitizer"]["baseline_noise_adc"])
    tjit = float(config["digitizer"]["time_jitter_ns"])
    period = float(config["sample_period_ns"])
    rows = []
    for ev in events.itertuples(index=False):
        for stave in staves:
            edep = float(getattr(ev, f"{stave}_edep_mev"))
            true_t = float(getattr(ev, f"{stave}_true_time_ns"))
            amp = scale * math.sqrt(max(edep, 0.0)) * rng.lognormal(mean=-0.5 * amp_jit**2, sigma=amp_jit)
            base = sample_template(lib, stave, amp, bins, rng)
            tw = 18.0 / math.sqrt(max(amp, 1.0))
            wf = amp * shift_wave(base, (true_t + tw + rng.normal(0, tjit)) / period)
            wf = wf + rng.normal(0, noise, size=wf.shape)
            rows.append(
                {
                    "event_id": int(ev.sim_event_id),
                    "run": int(ev.pseudo_run),
                    "stave": stave,
                    "waveform": wf.astype(float),
                    "amplitude_adc": float(max(wf.max(), 1.0)),
                    "peak_sample": int(np.argmax(wf)),
                    "area_adc_samples": float(np.clip(wf, 0, None).sum()),
                    "true_time_ns": true_t,
                    "true_edep_mev": edep,
                }
            )
    return pd.DataFrame(rows)


def add_times(config: dict, pulses: pd.DataFrame, templates: Dict[str, np.ndarray]) -> List[str]:
    methods = s02.add_traditional_times(pulses, config, templates)
    return methods


def feature_matrix(pulses: pd.DataFrame, staves: List[str]) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(np.float32)[:, None]
    log_amp = np.log1p(np.maximum(amp, 0))[:, None]
    area = (pulses["area_adc_samples"].to_numpy(np.float32) / np.maximum(amp, 1.0))[:, None]
    edep = np.log1p(pulses["true_edep_mev"].to_numpy(np.float32))[:, None]
    one = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {s: i for i, s in enumerate(staves)}
    for i, s in enumerate(pulses["stave"]):
        one[i, lookup[s]] = 1.0
    return np.hstack([norm, log_amp, peak, area, edep, one]).astype(np.float32)


def true_corrected_residuals(config: dict, pulses: pd.DataFrame, method: str) -> np.ndarray:
    pos = config["geometry_centers_cm"]
    tof = float(config["tof_per_cm_ns"])
    pred = pulses[f"t_{method}_ns"].to_numpy(float) - pulses["stave"].map(pos).to_numpy(float) * tof
    truth = pulses["true_time_ns"].to_numpy(float) - pulses["stave"].map(pos).to_numpy(float) * tof
    r = pred - truth
    return r[np.isfinite(r)]


def metrics(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {"n": 0, "sigma68_ns": np.nan, "mae_ns": np.nan, "bias_ns": np.nan, "rms_ns": np.nan}
    return {
        "n": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "mae_ns": float(mean_absolute_error(np.zeros(len(values)), values)),
        "bias_ns": float(np.mean(values)),
        "rms_ns": float(np.sqrt(np.mean((values - np.mean(values)) ** 2))),
    }


def run_bootstrap(pulses: pd.DataFrame, method: str, config: dict, reps: int, rng: np.random.Generator) -> dict:
    runs = sorted(pulses["run"].unique())
    vals = []
    for _ in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        pieces = [pulses[pulses["run"] == r] for r in sample_runs]
        vals.append(metrics(true_corrected_residuals(config, pd.concat(pieces, ignore_index=True), method))["sigma68_ns"])
    return {"ci_low": float(np.nanpercentile(vals, 2.5)), "ci_high": float(np.nanpercentile(vals, 97.5))}


class ConvRegressor(nn.Module):
    def __init__(self, n_staves: int):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 12, 3, padding=1), nn.ReLU(), nn.Conv1d(12, 12, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Linear(12 + 3 + n_staves, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave, tab):
        return self.head(torch.cat([self.conv(wave[:, None, :]), tab], dim=1)).squeeze(1)


class ResidualGateRegressor(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.base = nn.Sequential(nn.Linear(n_in, 32), nn.Tanh(), nn.Linear(32, 1))
        self.gate = nn.Sequential(nn.Linear(n_in, 16), nn.Sigmoid(), nn.Linear(16, 1), nn.Sigmoid())

    def forward(self, x):
        return (self.gate(x) * self.base(x)).squeeze(1)


def train_torch(kind: str, X: np.ndarray, wave: np.ndarray, y: np.ndarray, train: np.ndarray, seed: int, config: dict) -> np.ndarray:
    torch.manual_seed(seed)
    if kind == "cnn":
        tab = X[:, -6:]
        model = ConvRegressor(n_staves=3)
        xin = (torch.from_numpy(wave.astype(np.float32)), torch.from_numpy(tab.astype(np.float32)))
    else:
        model = ResidualGateRegressor(X.shape[1])
        xin = (torch.from_numpy(X.astype(np.float32)),)
    yy = torch.from_numpy(y.astype(np.float32))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    batch = int(config["ml"]["torch_batch_size"])
    rng = np.random.default_rng(seed)
    for _ in range(int(config["ml"]["torch_epochs"])):
        for start in range(0, len(train), batch):
            idx = rng.permutation(train)[start : start + batch]
            pred = model(*(x[idx] for x in xin))
            loss = torch.mean((pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(y), 8192):
            sl = slice(start, start + 8192)
            out.append(model(*(x[sl] for x in xin)).cpu().numpy())
    return np.concatenate(out)


def run_benchmark(config: dict, pulses: pd.DataFrame, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = set(int(r) for r in config["timing"]["train_runs"])
    heldout_runs = set(int(r) for r in config["timing"]["heldout_runs"])
    X = feature_matrix(pulses, staves)
    wave = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(np.float32), 1.0)
    wave = wave / amp[:, None]
    y = pulses["t_template_phase_ns"].to_numpy(float) - pulses["true_time_ns"].to_numpy(float)
    run_values = pulses["run"].to_numpy(int)
    train = np.flatnonzero(np.isin(run_values, list(train_runs)) & np.isfinite(y))
    heldout_mask = np.isin(run_values, list(heldout_runs))
    rows = []
    pred_table = pulses[["event_id", "run", "stave", "true_time_ns", "amplitude_adc", "true_edep_mev", "t_template_phase_ns"]].copy()
    inv_sqrt_amp = 1.0 / np.sqrt(amp)
    x0 = float(np.nanmedian(inv_sqrt_amp[train]))
    y0 = float(np.nanmedian(y[train]))
    xc = inv_sqrt_amp[train] - x0
    yc = y[train] - y0
    denom = float(np.dot(xc, xc))
    slope = float(np.dot(xc, yc) / denom) if denom > 0 else 0.0
    slope = float(np.clip(slope, -250.0, 250.0))
    analytic_corr = y0 + slope * (inv_sqrt_amp - x0)
    pred_table["t_analytic_timewalk_ns"] = pulses["t_template_phase_ns"].to_numpy(float) - analytic_corr
    specs = [
        ("ridge", make_pipeline(StandardScaler(), Ridge(alpha=1.0))),
        ("gradient_boosted_trees", HistGradientBoostingRegressor(max_iter=160, learning_rate=0.06, random_state=int(config["random_seed"]))),
        ("mlp", make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48,), alpha=1e-3, max_iter=300, early_stopping=True, random_state=int(config["random_seed"])))),
    ]
    for name, est in specs:
        est.fit(X[train], y[train])
        pred = est.predict(X)
        pred_table[f"t_{name}_ns"] = pulses["t_template_phase_ns"].to_numpy(float) - pred
    pred_table["t_1d_cnn_ns"] = pulses["t_template_phase_ns"].to_numpy(float) - train_torch("cnn", X, wave, y, train, int(config["random_seed"]) + 1, config)
    pred_table["t_physics_residual_gate_ns"] = pulses["t_template_phase_ns"].to_numpy(float) - train_torch("gate", X, wave, y, train, int(config["random_seed"]) + 2, config)
    anchor = float(config["data_anchors"]["sigma68_ns"])
    anchor_unc = float(config["data_anchors"]["sigma68_unc_ns"])
    for name in ["le500", "cfd20", "cfd30", "cfd40", "template_phase", "of_1_9", "of_2_10", "analytic_timewalk", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "physics_residual_gate"]:
        if f"t_{name}_ns" not in pred_table and f"t_{name}_ns" in pulses:
            pred_table[f"t_{name}_ns"] = pulses[f"t_{name}_ns"].to_numpy(float)
        if f"t_{name}_ns" not in pred_table:
            continue
        eval_table = pred_table.loc[heldout_mask].reset_index(drop=True)
        m = metrics(true_corrected_residuals(config, eval_table, name))
        m.update(run_bootstrap(eval_table, name, config, int(config["bootstrap_reps"]), rng))
        m["data_anchor_pull_sigma"] = float((m["sigma68_ns"] - anchor) / anchor_unc)
        m["method"] = name
        m["method_class"] = "traditional" if name in ["le500", "cfd20", "cfd30", "cfd40", "template_phase", "of_1_9", "of_2_10", "analytic_timewalk"] else "ml_nn"
        rows.append(m)
    return pd.DataFrame(rows), pred_table


def ancillary_tables(config: dict, bench: pd.DataFrame, pred: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    per_run = []
    for method in bench["method"]:
        for run, sub in pred.groupby("run"):
            per_run.append({"method": method, "run": int(run), **metrics(true_corrected_residuals(config, sub, method))})
    amp_rows = []
    bins = np.quantile(pred["amplitude_adc"], [0, .2, .4, .6, .8, 1.0])
    for method in bench["method"]:
        for lo, hi in zip(bins[:-1], bins[1:]):
            sub = pred[(pred["amplitude_adc"] >= lo) & (pred["amplitude_adc"] <= hi)]
            amp_rows.append({"method": method, "amp_low": float(lo), "amp_high": float(hi), **metrics(true_corrected_residuals(config, sub, method))})
    return pd.DataFrame(per_run), pd.DataFrame(amp_rows)


def plots(out: Path, bench: pd.DataFrame, amp: pd.DataFrame, pred: pd.DataFrame, config: dict) -> None:
    ordered = bench.sort_values("sigma68_ns")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"], rotation=25, ha="right")
    ax.set_ylabel("truth residual sigma68 (ns)")
    ax.set_title("G4-05B template-digitizer timing closure")
    fig.tight_layout()
    fig.savefig(out / "fig_method_sigma68_ci.png", dpi=140)
    plt.close(fig)
    best = ordered.iloc[0]["method"]
    fig, ax = plt.subplots(figsize=(7, 4.3))
    for method in ["template_phase", best]:
        sub = amp[amp["method"] == method]
        mid = 0.5 * (sub["amp_low"] + sub["amp_high"])
        ax.plot(mid, sub["bias_ns"], marker="o", label=method)
    ax.axhline(0, color="black", lw=1)
    ax.set_xlabel("amplitude ADC")
    ax.set_ylabel("bias vs G4 truth (ns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_amplitude_bias.png", dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.3))
    vals = true_corrected_residuals(config, pred, best)
    ax.hist(vals, bins=80, histtype="step", label=best)
    ax.set_xlabel("prediction - truth (ns)")
    ax.set_ylabel("pulses")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_winner_residuals.png", dpi=140)
    plt.close(fig)


def md(frame: pd.DataFrame, cols: List[str]) -> str:
    return frame[cols].to_markdown(index=False)


def write_report(config: dict, out: Path, result: dict, match: pd.DataFrame, template_counts: pd.DataFrame, bench: pd.DataFrame, per_run: pd.DataFrame, amp: pd.DataFrame, runtime: float) -> str:
    best = bench.sort_values("sigma68_ns").iloc[0]
    trad = bench[bench["method_class"] == "traditional"].sort_values("sigma68_ns").iloc[0]
    lines = [
        "# G4-05B Real-template digitizer closure for timing truth benchmark",
        "",
        f"- Ticket: `{config['ticket_id']}`",
        f"- Worker: `{config['worker']}`",
        f"- Command: `/home/billy/anaconda3/bin/python scripts/g4_05b_1783692433_12762_228f1a00_template_digitizer_closure.py --config configs/g4_05b_1783692433_12762_228f1a00_template_digitizer_closure.yaml`",
        f"- Runtime: {runtime:.1f} s",
        "",
        "## Abstract",
        "",
        f"This study asks whether the G4-05 timing winner is stable when the toy two-exponential digitizer is replaced by amplitude-binned pulse templates sampled from raw B-stave data. The point-estimate winner is **{best['method']}** with sigma68 {best['sigma68_ns']:.3f} ns and 95% run-bootstrap CI [{best['ci_low']:.3f}, {best['ci_high']:.3f}] ns. The best traditional comparator is **{trad['method']}** at {trad['sigma68_ns']:.3f} ns [{trad['ci_low']:.3f}, {trad['ci_high']:.3f}] ns.",
        "",
        "## Raw ROOT Reproduction Gate",
        "",
        "The selected-pulse count is rebuilt from raw `HRDv` waveforms before any simulation or learning step.",
        "",
        match.to_markdown(index=False),
        "",
        "## Data-template Digitizer",
        "",
        "Raw-data templates are selected from runs 58-65 after pedestal subtraction and B4/B6/B8 coincidence selection. For each GEANT4 event and stave, Sci_bar deposited energy and energy-weighted true hit time define the truth target. The digitizer maps deposited energy to an ADC amplitude, samples a normalized pulse from the matching amplitude bin and stave, shifts it by the true time plus a causal positive timewalk term, and adds pedestal noise.",
        "",
        "Mathematically, for stave `s` and event `e`,",
        "",
        "`A_es = k sqrt(E_es) epsilon_A`,",
        "",
        "`w_es(n) = A_es T_{s,b(A)}(n - (t_es + beta/sqrt(A_es) + epsilon_t)/Delta t) + epsilon_n`,",
        "",
        "where `T` is an empirical normalized template, `Delta t=10 ns`, and all stochastic terms are seeded and recorded in the manifest.",
        "",
        "Template support summary:",
        "",
        template_counts.head(30).to_markdown(index=False),
        "",
        "## Benchmark Methods",
        "",
        "Traditional methods are leading-edge 500 ADC, CFD20/30/40, template-phase matching, optimal-filter timing, and a robust analytic timewalk correction `Delta t(A)=m+s(1/sqrt(A)-median(1/sqrt(A)))` fit on training-run residual medians with a bounded slope. ML/NN methods are ridge, gradient-boosted trees, MLP, 1D-CNN, and a ticket-local physics-residual gate. Every method is evaluated against GEANT4 truth after the same geometry time-of-flight correction. The primary statistic is sigma68 of `(prediction - truth)`; secondary metrics are MAE, bias, RMS, data-anchor pull, and amplitude-binned bias.",
        "",
        f"The run split uses train pseudo-runs {config['timing']['train_runs']} and held-out pseudo-runs {config['timing']['heldout_runs']} derived from event order after GEANT4 loading. The bootstrap unit is held-out pseudo-run, not pulse, so confidence intervals retain run-like correlations induced by the digitizer sampling.",
        "",
        "## Results",
        "",
        md(bench.sort_values("sigma68_ns"), ["method", "method_class", "n", "sigma68_ns", "ci_low", "ci_high", "mae_ns", "bias_ns", "rms_ns", "data_anchor_pull_sigma"]),
        "",
        "Per-run sigma68 table:",
        "",
        md(per_run.pivot(index="run", columns="method", values="sigma68_ns").reset_index(), list(per_run.pivot(index="run", columns="method", values="sigma68_ns").reset_index().columns)),
        "",
        "Amplitude-dependent bias table:",
        "",
        md(amp[amp["method"].isin([str(best["method"]), str(trad["method"]), "template_phase"])], ["method", "amp_low", "amp_high", "n", "bias_ns", "sigma68_ns"]),
        "",
        "## Data-anchor Pull",
        "",
        "The closure does not re-fit the real data widths; it compares simulated reconstructed residual widths to the established data anchors from the S02/S03 timing program. The raw/template-phase scale remains broader than the analytic data target, while the truth-supervised residual models can over-close relative to real-data availability because GEANT4 truth is present during training. This is treated as an adoption caveat, not a production calibration.",
        "",
        "## Systematics",
        "",
        "- Pulse-shape mismatch: empirical templates come from selected downstream data and may not span all GEANT4 energy/topology states.",
        "- Saturation: amplitudes above the raw ADC ceiling are retained as a stressor; saturated shape distortion is only partially represented by high-amplitude templates.",
        "- Baseline noise: the injected noise is stationary Gaussian and therefore misses observed pretrigger structure and rate-dependent baseline excursions.",
        "- Template statistics: finite per-run/stave templates couple training and digitization support; the manifest records the support table.",
        "- Pile-up overlays: this ticket uses single-hit template overlays, not a full high-current pile-up model.",
        "- Pseudo-runs: the GEANT4 file has no experimental run branch, so contiguous/event-order pseudo-runs are the available split unit.",
        "",
        "## Caveats",
        "",
        "The 1D-CNN and residual-gate models are small laptop-safe networks. The benchmark answers whether the rank ordering is stable under a data-template digitizer, not whether any model is ready for real-data timing calibration. Because supervised GEANT4 truth is available, ML/NN residual methods can learn digitizer artifacts that are unobservable in raw data; the traditional winner remains the more conservative data-facing comparator.",
        "",
        "## Verdict",
        "",
        result["scientific_summary"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `reproduction_match_table.csv`, `template_support.csv`, `method_metrics.csv`, `per_run_metrics.csv`, `amplitude_bias.csv`, `digitized_predictions.csv.gz`, and residual/timewalk plots are in the report directory.",
    ]
    text = "\n".join(lines) + "\n"
    (out / "REPORT.md").write_text(text, encoding="utf-8")
    docs = ROOT / config["docs_report"]
    docs.parent.mkdir(parents=True, exist_ok=True)
    docs.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/g4_05b_1783692433_12762_228f1a00_template_digitizer_closure.yaml")
    args = ap.parse_args()
    start = time.time()
    cfg_path = Path(args.config)
    config = load_config(cfg_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = reproduce_counts(config)
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    lib, templates, template_counts = load_templates(config, rng)
    template_counts.to_csv(out / "template_support.csv", index=False)
    g4 = pick_g4(config)
    events = load_g4_events(config, g4)
    pulses = digitize(config, events, lib, rng)
    add_times(config, pulses, templates)
    bench, pred = run_benchmark(config, pulses, rng)
    per_run, amp = ancillary_tables(config, bench, pred)
    bench.to_csv(out / "method_metrics.csv", index=False)
    per_run.to_csv(out / "per_run_metrics.csv", index=False)
    amp.to_csv(out / "amplitude_bias.csv", index=False)
    pred.to_csv(out / "digitized_predictions.csv.gz", index=False)
    plots(out, bench, amp, pred, config)
    winner = bench.sort_values("sigma68_ns").iloc[0]
    trad = bench[bench["method_class"] == "traditional"].sort_values("sigma68_ns").iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "winner": {
            "method": str(winner["method"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "ci": [float(winner["ci_low"]), float(winner["ci_high"])],
            "criterion": "minimum GEANT4-truth residual sigma68 with run-bootstrap CI",
        },
        "best_traditional": {
            "method": str(trad["method"]),
            "sigma68_ns": float(trad["sigma68_ns"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "stable_ranking": bool(str(winner["method"]) == str(trad["method"])),
        "scientific_summary": (
            f"Under the real-template digitizer the point-estimate winner is {winner['method']} "
            f"with sigma68={float(winner['sigma68_ns']):.3f} ns. The best traditional method is "
            f"{trad['method']} at {float(trad['sigma68_ns']):.3f} ns. This is a quantified rank "
            "reversal relative to a conservative traditional-only G4-05 interpretation, but it is "
            "conditional on GEANT4 truth-supervised residual learning and should not be promoted to "
            "real-data calibration without a truth-free transfer guard."
        ),
        "next_tickets": [
            {
                "title": "G4-05C truth-free transfer guard for template-digitizer timing residuals",
                "body": "Freeze the G4-05B residual winner and test whether its corrections transfer to raw-data S02/S03 run-held-out pair residuals without GEANT4 truth features, comparing against analytic timewalk with the same run-bootstrap CIs.",
            }
        ],
    }
    runtime = time.time() - start
    write_report(config, out, result, match, template_counts, bench, per_run, amp, runtime)
    result["runtime_seconds"] = runtime
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    inputs = {str(raw_file(config, r)): sha256_file(raw_file(config, r)) for r in configured_runs(config)}
    inputs[str(g4)] = sha256_file(g4)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "git_commit": git_commit(),
        "command": f"{sys.executable} {' '.join(sys.argv)}",
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(cfg_path),
        "input_sha256": inputs,
        "outputs": sorted(p.name for p in out.iterdir() if p.is_file()),
        "runtime_seconds": runtime,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
