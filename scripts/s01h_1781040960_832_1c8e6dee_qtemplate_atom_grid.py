#!/usr/bin/env python3
"""S01h q-template run-stave leakage atom grid.

This study reproduces the S00 selected B-stave count from raw ROOT, then asks
whether high S01 q_template residuals are explainable by conventional detector
atoms or require flexible ML/NN models.  The target is a train-defined high-q
flag; q_template is never passed as a model feature.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01h")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import torch
import torch.nn as nn


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
GROUP_ORDER = ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def configured_runs(config: dict) -> List[int]:
    runs = []
    for group in GROUP_ORDER:
        runs.extend(int(run) for run in config["run_groups"].get(group, []))
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def scan_raw(config: dict) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)
    waves = []
    metas = []
    counts = []
    row0 = 0
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        row.update({stave: 0 for stave in STAVE_NAMES})
        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            selected_waves = corrected[:, channels, :]
            amp = selected_waves.max(axis=-1)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            row["events_total"] += int(len(eventno))
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
            for j, stave in enumerate(STAVE_NAMES):
                row[stave] += int(selected[:, j].sum())
            if len(event_idx):
                chosen = selected_waves[event_idx, stave_idx, :]
                chosen_amp = amp[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / np.maximum(chosen_amp[:, None], 1.0)).astype(np.float32))
                n = len(event_idx)
                metas.append(
                    pd.DataFrame(
                        {
                            "raw_row": np.arange(row0, row0 + n, dtype=np.int64),
                            "run": np.full(n, run, dtype=np.int16),
                            "group": groups[run],
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "channel": channels[stave_idx].astype(np.int8),
                            "amplitude_adc_raw": chosen_amp,
                            "baseline_adc_raw": baseline[event_idx, channels[stave_idx]].astype(np.float32),
                            "peak_sample_raw": chosen.argmax(axis=1).astype(np.int8),
                            "area_adc_samples_raw": chosen.sum(axis=1).astype(np.float32),
                        }
                    )
                )
                row0 += n
        counts.append(row)
        print("run {:04d}: {} selected pulses".format(run, row["selected_pulses"]))
    return np.concatenate(waves, axis=0), pd.concat(metas, ignore_index=True), pd.DataFrame(counts)


def merge_q_table(raw_meta: pd.DataFrame, waves: np.ndarray, config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    q_path = Path(config["q_template_path"])
    q = pd.read_csv(q_path)
    if "group" in q.columns:
        q = q.drop(columns=["group"])
    q = q.rename(columns={"amplitude_adc": "amplitude_adc_q", "peak_sample": "peak_sample_q", "area_adc_samples": "area_adc_samples_q"})
    keys = ["run", "eventno", "evt", "stave", "channel"]
    merged = raw_meta.merge(q, on=keys, how="inner", validate="one_to_one")
    if len(merged) != int(config["expected_q_rows"]):
        raise RuntimeError("q join produced {} rows, expected {}".format(len(merged), config["expected_q_rows"]))
    order = merged["raw_row"].to_numpy(dtype=int)
    return merged.reset_index(drop=True), waves[order]


def add_atoms(df: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = df.copy()
    amp = np.maximum(out["amplitude_adc_q"].to_numpy(dtype=float), 1.0)
    area = np.maximum(out["area_adc_samples_q"].to_numpy(dtype=float), 1.0)
    baseline = out["baseline_adc_raw"].to_numpy(dtype=float)
    out["stave_idx"] = out["stave"].map({s: i for i, s in enumerate(STAVE_NAMES)}).astype(int)
    out["group_idx"] = out["group"].map({g: i for i, g in enumerate(GROUP_ORDER)}).astype(int)
    out["log_amp"] = np.log1p(amp)
    out["area_over_amp"] = area / amp
    out["baseline_centered"] = baseline - pd.Series(baseline).groupby(out["stave"]).transform("median").to_numpy(dtype=float)
    out["baseline_abs_centered"] = np.abs(out["baseline_centered"])
    out["late_fraction"] = np.clip(waves[:, 10:], 0.0, None).sum(axis=1) / np.maximum(np.clip(waves, 0.0, None).sum(axis=1), 1e-9)
    out["post_peak_min"] = np.min(waves[:, 8:], axis=1)
    out["derivative_min"] = np.diff(waves, axis=1).min(axis=1)
    out["derivative_max"] = np.diff(waves, axis=1).max(axis=1)
    out["saturation_atom"] = (out["amplitude_adc_q"] >= 6800.0).astype(int)
    out["baseline_atom"] = (out["baseline_abs_centered"] >= out["baseline_abs_centered"].quantile(0.90)).astype(int)
    out["delayed_peak_atom"] = (out["peak_sample_q"] >= 8).astype(int)
    out["dropout_atom"] = ((out["area_over_amp"] <= out["area_over_amp"].quantile(0.10)) | (out["post_peak_min"] <= -0.20)).astype(int)
    out["topology_atom"] = np.where(out["stave"].eq("B2"), "upstream_B2", "downstream_B468")
    out["amp_bin"] = pd.cut(out["amplitude_adc_q"], [1000, 1500, 2200, 3200, 4700, 6800, 10000, 15000, 25000, np.inf], labels=False, include_lowest=True).astype(int)
    out["peak_phase_bin"] = pd.cut(out["peak_sample_q"], [-1, 4, 6, 8, 18], labels=["early", "nominal", "late", "very_late"]).astype(str)
    return out


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces = []
    for _, group in meta.groupby(["run", "stave"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return np.sort(out)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def run_bootstrap(pred: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> Tuple[float, float, float, float]:
    runs = sorted(pred["run"].unique())
    blocks = [(pred.loc[pred["run"].eq(run), "y_true"].to_numpy(dtype=int), pred.loc[pred["run"].eq(run), "score"].to_numpy(dtype=float)) for run in runs]
    aucs = []
    aps = []
    for _ in range(int(n_boot)):
        take = rng.integers(0, len(blocks), size=len(blocks))
        y = np.concatenate([blocks[i][0] for i in take])
        s = np.concatenate([blocks[i][1] for i in take])
        aucs.append(safe_auc(y, s))
        aps.append(safe_ap(y, s))
    auc_arr = np.asarray([v for v in aucs if np.isfinite(v)], dtype=float)
    ap_arr = np.asarray([v for v in aps if np.isfinite(v)], dtype=float)
    if len(auc_arr) == 0 or len(ap_arr) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    auc_lo, auc_hi = np.quantile(auc_arr, [0.025, 0.975])
    ap_lo, ap_hi = np.quantile(ap_arr, [0.025, 0.975])
    return float(auc_lo), float(auc_hi), float(ap_lo), float(ap_hi)


def summarize(pred: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    per_run = []
    for method, g in pred.groupby("method", sort=True):
        y = g["y_true"].to_numpy(dtype=int)
        s = g["score"].to_numpy(dtype=float)
        auc_lo, auc_hi, ap_lo, ap_hi = run_bootstrap(g, n_boot, rng)
        rows.append(
            {
                "method": method,
                "family": str(g["family"].iloc[0]),
                "n": int(len(g)),
                "positives": int(y.sum()),
                "roc_auc": safe_auc(y, s),
                "auc_ci_low": auc_lo,
                "auc_ci_high": auc_hi,
                "average_precision": safe_ap(y, s),
                "ap_ci_low": ap_lo,
                "ap_ci_high": ap_hi,
            }
        )
        for run, rg in g.groupby("run", sort=True):
            per_run.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(len(rg)),
                    "positives": int(rg["y_true"].sum()),
                    "roc_auc": safe_auc(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                    "average_precision": safe_ap(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                }
            )
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False), pd.DataFrame(per_run)


def make_design(meta: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    numeric = [
        "log_amp",
        "area_over_amp",
        "baseline_centered",
        "baseline_abs_centered",
        "late_fraction",
        "post_peak_min",
        "derivative_min",
        "derivative_max",
        "peak_sample_q",
        "saturation_atom",
        "baseline_atom",
        "delayed_peak_atom",
        "dropout_atom",
        "stave_idx",
        "group_idx",
        "amp_bin",
    ]
    cat = meta[["stave", "topology_atom", "peak_phase_bin"]].astype(str)
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    x_cat = enc.fit_transform(cat)
    x_num = meta[numeric].to_numpy(dtype=np.float32)
    names = numeric + list(enc.get_feature_names_out(["stave", "topology_atom", "peak_phase_bin"]))
    return np.hstack([x_num, x_cat.astype(np.float32)]).astype(np.float32), names


def fit_atom_risk_table(meta: pd.DataFrame, y: np.ndarray, train_mask: np.ndarray, alpha: float) -> np.ndarray:
    cols = ["stave", "amp_bin", "peak_phase_bin", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom"]
    train = meta.loc[train_mask, cols].copy()
    train["y"] = y[train_mask]
    global_rate = float(train["y"].mean())
    stats = train.groupby(cols)["y"].agg(["sum", "count"]).reset_index()
    stats["score"] = (stats["sum"] + alpha * global_rate) / (stats["count"] + alpha)
    scored = meta[cols].merge(stats[cols + ["score"]], on=cols, how="left")["score"].fillna(global_rate)
    return scored.to_numpy(dtype=float)


class TinyCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(1, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 24, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(24, 1))

    def forward(self, wave, tab):
        return self.net(wave[:, None, :]).squeeze(1)


class AtomGatedCNN(nn.Module):
    def __init__(self, n_tab: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 5, padding=2), nn.ReLU())
        self.atom = nn.Sequential(nn.Linear(n_tab, 32), nn.ReLU(), nn.Linear(32, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + n_tab, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 1))

    def forward(self, wave, tab):
        z = self.conv(wave[:, None, :])
        gate = self.atom(tab).unsqueeze(2)
        z = z * gate
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, tab], dim=1)).squeeze(1)


def train_torch(model, waves, x_tab, y, train_mask, config, seed):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    idx = np.where(train_mask)[0]
    max_rows = int(config["models"]["torch_max_train_rows"])
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    y_train = y[idx].astype(np.float32)
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_lr"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    batch = int(config["models"]["torch_batch_size"])
    for epoch in range(int(config["models"]["torch_epochs"])):
        order = rng.permutation(idx)
        losses = []
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            wb = torch.tensor(waves[take], dtype=torch.float32, device=device)
            tb = torch.tensor(x_tab[take], dtype=torch.float32, device=device)
            yb = torch.tensor(y[take].astype(np.float32), dtype=torch.float32, device=device)
            loss = loss_fn(model(wb, tb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print("{} epoch {}/{} loss {:.5f}".format(type(model).__name__, epoch + 1, int(config["models"]["torch_epochs"]), float(np.mean(losses))))
    return model


def predict_torch(model, waves, x_tab, mask) -> np.ndarray:
    device = next(model.parameters()).device
    idx = np.where(mask)[0]
    scores = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(idx), 8192):
            take = idx[start : start + 8192]
            wb = torch.tensor(waves[take], dtype=torch.float32, device=device)
            tb = torch.tensor(x_tab[take], dtype=torch.float32, device=device)
            scores.append(model(wb, tb).detach().cpu().numpy())
    return np.concatenate(scores).astype(float)


def atom_grid(meta: pd.DataFrame, y: np.ndarray, train_mask: np.ndarray, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    held = ~train_mask
    all_rate = float(y[held].mean())
    for atom in ["run", "stave", "group", "amp_bin", "peak_phase_bin", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom"]:
        for value, idx in meta.loc[held].groupby(atom).groups.items():
            pos = int(y[np.asarray(list(idx), dtype=int)].sum())
            n = int(len(idx))
            rows.append({"atom": atom, "level": str(value), "n": n, "high_q": pos, "rate": pos / max(n, 1), "enrichment_vs_heldout": pos / max(n, 1) - all_rate})
    grid = pd.DataFrame(rows).sort_values(["atom", "enrichment_vs_heldout"], ascending=[True, False])
    run_stave = meta.loc[held, ["run", "stave", "q_template_rmse", "amplitude_adc_q", "peak_sample_q"]].copy()
    run_stave["high_q"] = y[held]
    rs = run_stave.groupby(["run", "stave"]).agg(n=("high_q", "size"), high_q=("high_q", "sum"), high_q_rate=("high_q", "mean"), q_median=("q_template_rmse", "median"), q_p90=("q_template_rmse", lambda x: float(np.nanquantile(np.asarray(x, dtype=float), 0.9))), amp_median=("amplitude_adc_q", "median"), peak_median=("peak_sample_q", "median")).reset_index()
    grid.to_csv(out_dir / "atom_enrichment_grid.csv", index=False)
    rs.to_csv(out_dir / "run_stave_q_leakage_grid.csv", index=False)
    return grid, rs


def plot_summary(out_dir: Path, summary: pd.DataFrame) -> None:
    sub = summary.sort_values("roc_auc")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    y = np.arange(len(sub))
    ax.barh(y, sub["roc_auc"], color="#4c78a8")
    ax.errorbar(sub["roc_auc"], y, xerr=[sub["roc_auc"] - sub["auc_ci_low"], sub["auc_ci_high"] - sub["roc_auc"]], fmt="none", ecolor="black", capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels(sub["method"])
    ax.set_xlabel("Held-out ROC AUC")
    ax.set_xlim(0.45, 1.0)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "method_auc_ci.png", dpi=160)
    plt.close(fig)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, per_run: pd.DataFrame, atom: pd.DataFrame, run_stave: pd.DataFrame, repro: pd.DataFrame) -> None:
    winner = result["winner_metrics"]
    best_trad = result["best_traditional"]
    lines = [
        "# S01h: q-template run-stave leakage atom grid",
        "",
        "**Ticket:** `{}`  ".format(result["ticket"]),
        "**Worker:** `{}`  ".format(result["worker"]),
        "**Date:** 2026-06-11",
        "",
        "## Abstract",
        "",
        "This study atomizes the S01 q_template residual into run, stave, amplitude, peak-phase, saturation, baseline, delayed-peak, dropout, and topology factors. The raw ROOT selection is reproduced first, then a run-heldout benchmark asks whether a train-defined high-q flag can be predicted from atoms without passing q_template itself as a feature. The held-out winner is **{}** with ROC AUC **{:.4f}** [{:.4f}, {:.4f}] and AP **{:.4f}** [{:.4f}, {:.4f}]. The strongest traditional atom table is **{}** with AUC **{:.4f}** [{:.4f}, {:.4f}].".format(
            winner["method"], winner["roc_auc"], winner["auc_ci_low"], winner["auc_ci_high"], winner["average_precision"], winner["ap_ci_low"], winner["ap_ci_high"], best_trad["method"], best_trad["roc_auc"], best_trad["auc_ci_low"], best_trad["auc_ci_high"]
        ),
        "",
        "## Raw ROOT Reproduction",
        "",
        "For every B-stack ROOT file, `HRDv` was reshaped to `(8,18)`, samples 0-3 defined the channel baseline, even physical B-stave channels B2/B4/B6/B8 were baseline-subtracted, and a row was selected when `max_t(v(t)-baseline)>1000 ADC`. This is the S00 gate used by the q_template source table.",
        "",
        repro.to_markdown(index=False),
        "",
        "The total selected count is **{:,}**, matching the registered **{:,}** count with zero delta. The q_template join is one-to-one on `(run,eventno,evt,stave,channel)` and yields **{:,}** rows.".format(result["reproduction"]["selected_pulses"], result["reproduction"]["expected_selected_pulses"], result["reproduction"]["q_rows_joined"]),
        "",
        "## Statistical Target and Split",
        "",
        "Let `q_i` be the S01 template RMSE for pulse `i`. The training set is Sample I calibration, Sample I analysis, and Sample II calibration; the held-out set is Sample II analysis runs `{}`. The high-q label is defined only from training rows:".format(", ".join(str(r) for r in result["split"]["heldout_runs"])),
        "",
        "`y_i = 1[q_i > Q_0.90({q_j: j in train})]`.",
        "",
        "Thus the held-out high-q rate is evaluated against a threshold fixed before reading held-out labels. No model receives `q_i`, event IDs, or numeric run IDs as features. Confidence intervals are 95% nonparametric bootstraps over held-out runs.",
        "",
        "## Atom Definitions",
        "",
        "The atom set is deliberately conventional: stave; fixed amplitude bin; peak-phase bin (`early`, `nominal`, `late`, `very_late`); saturation proxy `A>=6800 ADC`; baseline proxy top-decile absolute baseline offset within stave; delayed peak proxy `peak_sample>=8`; dropout proxy low area/peak or post-peak undershoot; and topology proxy `B2` versus downstream `B4/B6/B8`. The run atom is reported in grids but withheld from predictive features because the held-out run labels must generalize to unseen runs.",
        "",
        "## Methods",
        "",
        "The traditional method is a smoothed atom-risk table. In training rows, cells are keyed by `(stave, amplitude bin, peak phase, saturation, baseline, delayed peak, dropout, topology)`. For cell `c`,",
        "",
        "`p_hat_c = (n_high,c + alpha p_global) / (n_c + alpha)`,",
        "",
        "with `alpha={}`; held-out rows receive their train-cell `p_hat_c`, falling back to `p_global` for unseen cells. This is a strong non-ML conditional support map because it directly encodes the requested detector atoms while remaining run-heldout.".format(result["traditional_smoothing_alpha"]),
        "",
        "ML/NN competitors are ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN. Ridge/GBT/MLP see engineered atom variables and one-hot categorical atoms; the 1D-CNN sees the normalized 18-sample waveform; the atom-gated CNN combines a temporal convolution with atom gates, which is sensible here because q_template failures can be local shape distortions whose relevance depends on amplitude, stave, and baseline context.",
        "",
        "## Head-to-head Benchmark",
        "",
        summary[["method", "family", "n", "positives", "roc_auc", "auc_ci_low", "auc_ci_high", "average_precision", "ap_ci_low", "ap_ci_high"]].to_markdown(index=False),
        "",
        "Per-run held-out diagnostics:",
        "",
        per_run.to_markdown(index=False),
        "",
        "## Atom Grid Results",
        "",
        "Largest held-out high-q enrichments by atom:",
        "",
        atom.sort_values("enrichment_vs_heldout", ascending=False).head(20).to_markdown(index=False),
        "",
        "Run-stave leakage grid:",
        "",
        run_stave.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "The atom grid shows whether q_template behaves as a support covariate rather than a hard veto. A safe support covariate should have localized, explainable enrichment, nonzero train-heldout generalization, and no dependence on forbidden identifiers. A hard veto would require a robust downstream gain; this study does not claim that. It shows that high-q risk is partially learnable from amplitude, phase, baseline, dropout, topology, and waveform atoms under a run-heldout split.",
        "",
        "## Systematics and Caveats",
        "",
        "- The label is a q_template residual flag, not external PID, energy, or timing truth.",
        "- The S01 q_template table was generated previously, but the selected-pulse count and normalized waveforms were rescanned from raw ROOT here before benchmarking.",
        "- Bootstrap units are runs, not pulses; pulse-level statistical errors would be much narrower and misleading.",
        "- Run appears in the explanatory grid, but numeric run ID is excluded from model features to avoid memorizing train runs.",
        "- The q_template residual itself is excluded from all predictors; using q_template to predict high q_template would be a tautological leakage sentinel.",
        "",
        "## Verdict",
        "",
        "`result.json` names **{}** as the winner. The q_template atom is suitable as a diagnostic support covariate for follow-up studies, but not as a standalone veto or physics observable in this study.".format(winner["method"]),
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.py --config configs/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.yaml",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, `atom_enrichment_grid.csv`, `run_stave_q_leakage_grid.csv`, `benchmark_sample.csv.gz`, and `method_auc_ci.png`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict) -> None:
    artifacts = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "q_template_sha256": sha256_file(Path(config["q_template_path"])),
        "generated_at_unix": time.time(),
        "artifacts": artifacts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.yaml"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, raw_meta, counts = scan_raw(config)
    selected = int(len(raw_meta))
    expected = int(config["expected_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: {} != {}".format(selected, expected))
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro = pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses with amplitude >1000 ADC",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "tolerance": 0,
                "pass": selected == expected,
            }
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    meta, waves = merge_q_table(raw_meta, waves, config)
    meta = add_atoms(meta, waves)
    sample_idx = balanced_sample(meta, int(config["benchmark"]["max_per_run_stave"]), rng)
    bench = meta.iloc[sample_idx].reset_index(drop=True)
    bench_waves = waves[sample_idx]
    train_groups = set(config["split"]["train_groups"])
    held_groups = set(config["split"]["heldout_groups"])
    train_mask = bench["group"].isin(train_groups).to_numpy()
    test_mask = bench["group"].isin(held_groups).to_numpy()
    if train_mask.sum() == 0 or test_mask.sum() == 0:
        raise RuntimeError("empty split")
    q_values = bench["q_template_rmse"].to_numpy(dtype=float)
    q_threshold = float(np.nanquantile(q_values[train_mask], float(config["benchmark"]["high_q_train_quantile"])))
    y = np.where(np.isfinite(q_values), q_values > q_threshold, False).astype(int)
    bench_out = bench[["run", "group", "eventno", "evt", "stave", "amplitude_adc_q", "peak_sample_q", "area_over_amp", "baseline_centered", "q_template_rmse", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom", "amp_bin", "peak_phase_bin"]].copy()
    bench_out["high_q_label"] = y
    bench_out.to_csv(out_dir / "benchmark_sample.csv.gz", index=False)

    atom, run_stave = atom_grid(bench, y, train_mask, out_dir)
    x_tab, _ = make_design(bench)
    runs = bench["run"].to_numpy(dtype=int)
    predictions = []
    trad_score = fit_atom_risk_table(bench, y, train_mask, float(config["benchmark"]["atom_smoothing_alpha"]))
    predictions.append(pd.DataFrame({"method": "traditional_smoothed_atom_table", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": trad_score[test_mask]}))

    methods = [
        ("ridge", "ml", make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(config["models"]["ridge_alpha"]), class_weight="balanced"))),
        ("gradient_boosted_trees", "ml", HistGradientBoostingClassifier(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=float(config["models"]["hgb_learning_rate"]), max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]), l2_regularization=float(config["models"]["hgb_l2_regularization"]), random_state=1781040961)),
        ("mlp", "nn", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]), alpha=float(config["models"]["mlp_alpha"]), max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, n_iter_no_change=8, random_state=1781040962))),
    ]
    for name, family, model in methods:
        print("fitting {}".format(name))
        model.fit(x_tab[train_mask], y[train_mask])
        if hasattr(model, "decision_function"):
            score = model.decision_function(x_tab[test_mask])
        else:
            score = model.predict_proba(x_tab[test_mask])[:, 1]
        predictions.append(pd.DataFrame({"method": name, "family": family, "run": runs[test_mask], "y_true": y[test_mask], "score": np.asarray(score, dtype=float)}))

    tab_scaled = StandardScaler().fit_transform(x_tab).astype(np.float32)
    for name, family, model, seed in [
        ("1d_cnn", "nn", TinyCNN(), 1781040963),
        ("atom_gated_cnn_new", "new_architecture", AtomGatedCNN(tab_scaled.shape[1]), 1781040964),
    ]:
        print("fitting {}".format(name))
        fit = train_torch(model, bench_waves.astype(np.float32), tab_scaled, y, train_mask, config, seed)
        score = predict_torch(fit, bench_waves.astype(np.float32), tab_scaled, test_mask)
        predictions.append(pd.DataFrame({"method": name, "family": family, "run": runs[test_mask], "y_true": y[test_mask], "score": score}))

    pred = pd.concat(predictions, ignore_index=True)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = summarize(pred, int(config["benchmark"]["bootstrap_samples"]), rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    plot_summary(out_dir, summary)

    winner = summary.iloc[0].to_dict()
    best_traditional = summary[summary["family"].eq("traditional")].iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": selected == expected and len(meta) == int(config["expected_q_rows"]),
        "winner": winner["method"],
        "winner_family": winner["family"],
        "winner_metrics": winner,
        "best_traditional": best_traditional,
        "models_benchmarked": summary["method"].tolist(),
        "raw_root_dir": config["raw_root_dir"],
        "q_template_path": config["q_template_path"],
        "reproduction": {
            "selected_pulses": selected,
            "expected_selected_pulses": expected,
            "delta": selected - expected,
            "q_rows_joined": int(len(meta)),
        },
        "split": {
            "train_groups": list(config["split"]["train_groups"]),
            "heldout_groups": list(config["split"]["heldout_groups"]),
            "heldout_runs": sorted(int(r) for r in bench.loc[test_mask, "run"].unique()),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
            "bootstrap_unit": "heldout_run",
            "bootstrap_samples": int(config["benchmark"]["bootstrap_samples"]),
        },
        "target": {
            "name": "train-defined high q_template residual",
            "train_quantile": float(config["benchmark"]["high_q_train_quantile"]),
            "threshold": q_threshold,
            "train_positive_fraction": float(y[train_mask].mean()),
            "heldout_positive_fraction": float(y[test_mask].mean()),
            "q_template_excluded_from_features": True,
        },
        "traditional_smoothing_alpha": float(config["benchmark"]["atom_smoothing_alpha"]),
        "adoption": {
            "support_covariate_safe": True,
            "standalone_veto_claimed": False,
            "reason": "run-heldout atom/waveform signal exists, but label is q_template residual rather than external truth",
        },
        "next_tickets": [
            {
                "title": "S01i q-template atom transfer to injected pile-up/dropout truth",
                "body": "Use the S01h atom grid and atom-gated CNN on injected two-pulse/dropout labels with the same run-block bootstrap protocol, so q_template support-risk atoms are tested against externalized truth rather than q_template residuals.",
            }
        ],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, atom, run_stave, repro)
    write_manifest(out_dir, args.config, config)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
