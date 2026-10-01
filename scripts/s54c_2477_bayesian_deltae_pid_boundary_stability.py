#!/usr/bin/env python3
"""S54c Bayesian deltaE-E PID boundary stability benchmark.

The ticket asks for a raw-ROOT reproduction gate and a method bakeoff comparing
a strong traditional PID template against ridge, boosted trees, MLP, 1D-CNN,
and a new architecture.  No external PID truth file is mounted in this worker,
so this study freezes and audits a raw-data weak PID boundary derived from
B-stack deltaE/E and penetration depth.  The report is explicit about that
systematic: the result is a boundary-stability benchmark, not a particle-ID
truth claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s54c_2477_bayesian_deltae_pid_boundary_stability.json"
STAVE_NAMES = ["B2", "B4", "B6", "B8"]
DEPTH = np.asarray([0.0, 1.0, 2.0, 3.0], dtype=np.float64)


def load_config() -> dict:
    with CONFIG.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_file(cfg: dict, run: int) -> Path:
    return ROOT / cfg["raw_root_dir"] / f"hrdb_run_{run:04d}.root"


def configured_runs(cfg: dict) -> list[int]:
    runs: list[int] = []
    for values in cfg["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def iter_raw(path: Path, branches: list[str], step_size: int = 20000):
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waves: np.ndarray, baseline_idx: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waves[..., baseline_idx], axis=-1)
    corrected = waves - baseline[..., None]
    amp = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amp, peak, area


def cfd_time(wf: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.nanmax(wf))
    if not np.isfinite(amp) or amp <= 0:
        return float("nan")
    threshold = amp * fraction
    above = np.flatnonzero(wf >= threshold)
    if len(above) == 0:
        return float("nan")
    j = int(above[0])
    if j <= 0:
        return float(j)
    y0, y1 = float(wf[j - 1]), float(wf[j])
    if y1 <= y0:
        return float(j)
    return float(j - 1 + (threshold - y0) / (y1 - y0))


def reproduce_counts(cfg: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    channels = np.asarray([int(cfg["staves"][name]) for name in STAVE_NAMES])
    nsamp = int(cfg["samples_per_channel"])
    cut = float(cfg["amplitude_cut_adc"])
    total = 0
    sample_ii = {name: 0 for name in STAVE_NAMES}
    sample_ii["selected_pulses"] = 0
    for run in configured_runs(cfg):
        path = raw_file(cfg, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_raw(path, ["HRDv"]):
            data = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waves = data[:, channels, :]
            _corr, amp, _peak, _area = pulse_quantities(waves, baseline_idx)
            selected = amp > cut
            total += int(selected.sum())
            if run in cfg["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(STAVE_NAMES):
                    sample_ii[stave] += int(selected[:, i].sum())
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(cfg["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in cfg["expected_counts"]["sample_ii_analysis"].items():
        rows.append({"quantity": f"sample_ii_analysis {key}", "report_value": int(value), "reproduced": int(sample_ii[key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def read_event_table(cfg: dict) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    channels = np.asarray([int(cfg["staves"][name]) for name in STAVE_NAMES])
    nsamp = int(cfg["samples_per_channel"])
    cut = float(cfg["amplitude_cut_adc"])
    max_events = int(cfg["max_events_per_run"])
    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    rows = []
    wave_rows = []
    event_id = 0
    for run in runs:
        candidates = []
        candidate_waves = []
        local = 0
        for batch in iter_raw(raw_file(cfg, run), ["EVENTNO", "EVT", "TRIGGER", "HRDv"], step_size=16000):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            trigger = np.asarray(batch["TRIGGER"]).astype(np.int64)
            data = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waves = data[:, channels, :]
            corrected, amp, peak, area = pulse_quantities(waves, baseline_idx)
            selected = amp.max(axis=1) > cut
            idx = np.flatnonzero(selected)
            for e in idx:
                wf = corrected[e]
                amp_e = amp[e].astype(float)
                area_e = area[e].astype(float)
                peak_e = peak[e].astype(float)
                cfd_e = np.asarray([cfd_time(wf[i]) for i in range(len(STAVE_NAMES))], dtype=float)
                total_amp = float(np.maximum(amp_e.sum(), 1.0))
                total_area = float(np.maximum(area_e.sum(), 1.0))
                late = float((area_e[2] + area_e[3]) / total_area)
                early = float((area_e[0] + area_e[1]) / total_area)
                dedx = float((area_e[0] + area_e[1]) / np.maximum(area_e[2] + area_e[3] + 1.0, 1.0))
                depth_mean = float(np.dot(DEPTH, np.maximum(area_e, 0.0)) / np.maximum(np.maximum(area_e, 0.0).sum(), 1.0))
                max_i = int(np.argmax(amp_e))
                candidates.append(
                    {
                        "event_id": event_id,
                        "source_run": int(run),
                        "split": "train" if run in cfg["benchmark_runs"]["train"] else "heldout",
                        "EVENTNO": int(eventno[e]),
                        "EVT": int(evt[e]),
                        "TRIGGER": int(trigger[e]),
                        "raw_event_ordinal": int(local + e),
                        "max_stave": STAVE_NAMES[max_i],
                        "total_amp_adc": total_amp,
                        "total_area_adc_samples": total_area,
                        "deltae_over_e": dedx,
                        "late_fraction": late,
                        "early_fraction": early,
                        "depth_mean": depth_mean,
                        "max_peak_sample": float(peak_e[max_i]),
                        "max_cfd20_sample": float(cfd_e[max_i]),
                        "pedestal_memory_adc": float(np.median(waves[e, :, baseline_idx])),
                        "saturation_mask": int(np.nanmax(amp_e) > 14000.0),
                    }
                )
                for i, name in enumerate(STAVE_NAMES):
                    candidates[-1][f"{name}_amp"] = float(amp_e[i])
                    candidates[-1][f"{name}_area"] = float(area_e[i])
                    candidates[-1][f"{name}_peak"] = float(peak_e[i])
                    candidates[-1][f"{name}_cfd20"] = float(cfd_e[i])
                candidate_waves.append(wf.astype(np.float32))
                event_id += 1
            local += len(eventno)
        if len(candidates) > max_events:
            take = np.sort(rng.choice(np.arange(len(candidates)), size=max_events, replace=False))
            candidates = [candidates[i] for i in take]
            candidate_waves = [candidate_waves[i] for i in take]
        rows.extend(candidates)
        wave_rows.extend(candidate_waves)
    frame = pd.DataFrame(rows).reset_index(drop=True)
    waves = np.stack(wave_rows).astype(np.float32)
    frame["event_id"] = np.arange(len(frame), dtype=np.int64)
    return frame, waves


def freeze_labels(frame: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = frame.copy()
    train = data[data["split"] == "train"]
    late_thr = float(train["late_fraction"].quantile(0.58))
    depth_thr = float(train["depth_mean"].quantile(0.58))
    dedx_thr = float(train["deltae_over_e"].quantile(0.42))
    score = (
        1.2 * (data["late_fraction"] - late_thr) / max(float(train["late_fraction"].std()), 1e-6)
        + 0.9 * (data["depth_mean"] - depth_thr) / max(float(train["depth_mean"].std()), 1e-6)
        - 0.45 * (data["deltae_over_e"] - dedx_thr) / max(float(train["deltae_over_e"].std()), 1e-6)
    )
    data["pid_boundary_score"] = score
    data["pid_label"] = (score >= 0.0).astype(int)
    data["energy_proxy_target"] = np.log1p(data["total_area_adc_samples"].clip(lower=1.0))
    data["timing_proxy_target"] = data["max_cfd20_sample"].fillna(data["max_peak_sample"])
    thresholds = pd.DataFrame(
        [
            {"quantity": "late_fraction_train_q58", "value": late_thr},
            {"quantity": "depth_mean_train_q58", "value": depth_thr},
            {"quantity": "deltae_over_e_train_q42", "value": dedx_thr},
            {"quantity": "train_positive_fraction", "value": float(data.loc[data["split"].eq("train"), "pid_label"].mean())},
            {"quantity": "heldout_positive_fraction", "value": float(data.loc[data["split"].eq("heldout"), "pid_label"].mean())},
        ]
    )
    thresholds.to_csv(out / "pid_boundary_definition.csv", index=False)
    return data, thresholds


FEATURE_COLS = [
    "total_amp_adc",
    "total_area_adc_samples",
    "deltae_over_e",
    "late_fraction",
    "early_fraction",
    "depth_mean",
    "max_peak_sample",
    "max_cfd20_sample",
    "pedestal_memory_adc",
    "saturation_mask",
] + [f"{s}_{kind}" for s in STAVE_NAMES for kind in ["amp", "area", "peak", "cfd20"]]


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    x = frame[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).copy()
    x = x.fillna(x.median(numeric_only=True)).fillna(0.0)
    return x.to_numpy(np.float32)


def auc_safe(y: np.ndarray, score: np.ndarray) -> float:
    try:
        return float(roc_auc_score(y, score))
    except Exception:
        return float("nan")


def bacc(y: np.ndarray, yhat: np.ndarray) -> float:
    parts = []
    for label in [0, 1]:
        mask = y == label
        if np.any(mask):
            parts.append(float(np.mean(yhat[mask] == label)))
    return float(np.mean(parts)) if parts else float("nan")


def ece(y: np.ndarray, score: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    n = len(y)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (score >= lo) & (score < hi if hi < 1.0 else score <= hi)
        if not np.any(mask):
            continue
        total += float(np.mean(mask)) * abs(float(np.mean(score[mask])) - float(np.mean(y[mask])))
    return total if n else float("nan")


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.nanpercentile(values, 84) - np.nanpercentile(values, 16)) / 2.0)


def gaussian_likelihood_prediction(train: pd.DataFrame, all_frame: pd.DataFrame) -> pd.DataFrame:
    cols = ["deltae_over_e", "late_fraction", "depth_mean", "total_area_adc_samples", "max_cfd20_sample", "pedestal_memory_adc"]
    xtr = train[cols].replace([np.inf, -np.inf], np.nan).fillna(train[cols].median(numeric_only=True)).to_numpy(float)
    ytr = train["pid_label"].to_numpy(int)
    xall = all_frame[cols].replace([np.inf, -np.inf], np.nan).fillna(train[cols].median(numeric_only=True)).to_numpy(float)
    means = {}
    vars_ = {}
    priors = {}
    for label in [0, 1]:
        mask = ytr == label
        means[label] = xtr[mask].mean(axis=0)
        vars_[label] = xtr[mask].var(axis=0) + 1e-6
        priors[label] = max(float(np.mean(mask)), 1e-6)
    logp = []
    for label in [0, 1]:
        lp = -0.5 * np.sum(((xall - means[label]) ** 2) / vars_[label] + np.log(vars_[label]), axis=1) + math.log(priors[label])
        logp.append(lp)
    logp0, logp1 = logp
    score = 1.0 / (1.0 + np.exp(np.clip(logp0 - logp1, -60, 60)))
    return pd.DataFrame(
        {
            "event_id": all_frame["event_id"],
            "method": "bayesian_deltae_template_likelihood",
            "pid_score": score,
            "energy_pred": np.log1p(all_frame["total_area_adc_samples"].to_numpy(float)),
            "timing_pred": all_frame["max_cfd20_sample"].to_numpy(float),
        }
    )


def sklearn_predictions(train: pd.DataFrame, all_frame: pd.DataFrame) -> list[pd.DataFrame]:
    xtr = feature_matrix(train)
    xall = feature_matrix(all_frame)
    y = train["pid_label"].to_numpy(int)
    e = train["energy_proxy_target"].to_numpy(float)
    t = train["timing_proxy_target"].to_numpy(float)
    specs = [
        (
            "ridge",
            make_pipeline(StandardScaler(), LogisticRegression(C=0.8, penalty="l2", solver="lbfgs", max_iter=500)),
            make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
            make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
        ),
        (
            "gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=140, learning_rate=0.055, l2_regularization=0.03, random_state=17),
            HistGradientBoostingRegressor(max_iter=130, learning_rate=0.055, l2_regularization=0.03, random_state=18),
            HistGradientBoostingRegressor(max_iter=130, learning_rate=0.055, l2_regularization=0.03, random_state=19),
        ),
        (
            "mlp",
            make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 24), alpha=0.002, max_iter=350, random_state=20, early_stopping=True)),
            make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=0.002, max_iter=350, random_state=21, early_stopping=True)),
            make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=0.002, max_iter=350, random_state=22, early_stopping=True)),
        ),
    ]
    preds = []
    for name, clf, ereg, treg in specs:
        clf.fit(xtr, y)
        ereg.fit(xtr, e)
        treg.fit(xtr, t)
        if hasattr(clf, "predict_proba"):
            score = clf.predict_proba(xall)[:, 1]
        else:
            raw = clf.decision_function(xall)
            score = 1.0 / (1.0 + np.exp(-raw))
        preds.append(
            pd.DataFrame(
                {
                    "event_id": all_frame["event_id"],
                    "method": name,
                    "pid_score": score,
                    "energy_pred": ereg.predict(xall),
                    "timing_pred": treg.predict(xall),
                }
            )
        )
    return preds


class CNN1D(nn.Module):
    def __init__(self, n_staves: int = 4, nsamp: int = 18):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_staves, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 16, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(16, 32),
            nn.ReLU(),
        )
        self.head = nn.Linear(32, 3)

    def forward(self, x):
        return self.head(self.net(x))


class TinyTransformer(nn.Module):
    def __init__(self, n_staves: int = 4, nsamp: int = 18):
        super().__init__()
        self.embed = nn.Linear(n_staves + 2, 24)
        layer = nn.TransformerEncoderLayer(d_model=24, nhead=4, dim_feedforward=48, dropout=0.05, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(24, 32), nn.ReLU(), nn.Linear(32, 3))

    def forward(self, x):
        b, c, t = x.shape
        seq = x.permute(0, 2, 1)
        pos = torch.linspace(0, 1, t, device=x.device).view(1, t, 1).expand(b, t, 1)
        sat = (seq > 0.93).float().amax(dim=2, keepdim=True)
        h = self.encoder(self.embed(torch.cat([seq, pos, sat], dim=2)))
        pooled = h.mean(dim=1)
        return self.head(pooled)


def neural_prediction(name: str, model: nn.Module, train: pd.DataFrame, all_frame: pd.DataFrame, waves: np.ndarray, cfg: dict, seed: int) -> pd.DataFrame:
    torch.manual_seed(seed)
    tr_idx = train.index.to_numpy()
    wav = waves.astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(wav[tr_idx]), 99), 1.0)
    wav = np.clip(wav / scale, -2.0, 2.0)
    y = train["pid_label"].to_numpy(np.float32)
    e = train["energy_proxy_target"].to_numpy(np.float32)
    t = train["timing_proxy_target"].to_numpy(np.float32)
    e_mu, e_sd = float(e.mean()), float(e.std() + 1e-6)
    t_mu, t_sd = float(t.mean()), float(t.std() + 1e-6)
    target = np.column_stack([y, (e - e_mu) / e_sd, (t - t_mu) / t_sd]).astype(np.float32)
    ds = TensorDataset(torch.from_numpy(wav[tr_idx]), torch.from_numpy(target))
    loader = DataLoader(ds, batch_size=int(cfg["ml"]["nn_batch_size"]), shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["ml"]["learning_rate"]), weight_decay=float(cfg["ml"]["weight_decay"]))
    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()
    model.train()
    for _epoch in range(int(cfg["ml"]["nn_epochs"])):
        for xb, yb in loader:
            opt.zero_grad()
            out = model(xb)
            loss = bce(out[:, 0], yb[:, 0]) + 0.25 * mse(out[:, 1], yb[:, 1]) + 0.25 * mse(out[:, 2], yb[:, 2])
            loss.backward()
            opt.step()
    model.eval()
    pred_parts = []
    with torch.no_grad():
        for start in range(0, len(wav), 1024):
            pred_parts.append(model(torch.from_numpy(wav[start : start + 1024])).numpy())
    raw = np.vstack(pred_parts)
    score = 1.0 / (1.0 + np.exp(-raw[:, 0]))
    return pd.DataFrame(
        {
            "event_id": all_frame["event_id"],
            "method": name,
            "pid_score": score,
            "energy_pred": raw[:, 1] * e_sd + e_mu,
            "timing_pred": raw[:, 2] * t_sd + t_mu,
        }
    )


def summarize_one(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["pid_label"].to_numpy(int)
    score = frame["pid_score"].to_numpy(float)
    yhat = (score >= 0.5).astype(int)
    cm = confusion_matrix(y, yhat, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    e_resid = frame["energy_pred"].to_numpy(float) - frame["energy_proxy_target"].to_numpy(float)
    t_resid = (frame["timing_pred"].to_numpy(float) - frame["timing_proxy_target"].to_numpy(float)) * 10.0
    return {
        "n": int(len(frame)),
        "pid_auc": auc_safe(y, score),
        "pid_balanced_accuracy": bacc(y, yhat),
        "pid_efficiency": float(tp / max(tp + fn, 1)),
        "pid_purity": float(tp / max(tp + fp, 1)),
        "confusion_tn": int(tn),
        "confusion_fp": int(fp),
        "confusion_fn": int(fn),
        "confusion_tp": int(tp),
        "calibration_ece": ece(y, score),
        "boundary_migration_rate": float(np.mean(yhat != y)),
        "energy_log_area_sigma68": sigma68(e_resid),
        "energy_log_area_bias": float(np.nanmedian(e_resid)),
        "timing_cfd20_sigma68_ns": sigma68(t_resid),
        "timing_cfd20_bias_ns": float(np.nanmedian(t_resid)),
        "pileup_veto_sensitivity": float(np.mean(yhat[frame["late_fraction"].to_numpy(float) > frame["late_fraction"].quantile(0.75)])) if len(frame) else float("nan"),
        "saturation_mask_sensitivity": float(np.mean(yhat[frame["saturation_mask"].to_numpy(int) == 1])) if np.any(frame["saturation_mask"].to_numpy(int) == 1) else float("nan"),
        "pedestal_transfer_span": float(frame.groupby(pd.qcut(frame["pedestal_memory_adc"], 3, duplicates="drop"))["pid_score"].mean().max() - frame.groupby(pd.qcut(frame["pedestal_memory_adc"], 3, duplicates="drop"))["pid_score"].mean().min()) if len(frame) > 5 else float("nan"),
    }


def summarize(joined: pd.DataFrame, cfg: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row = {"method": method}
        row.update(summarize_one(group))
        rows.append(row)
    overall = pd.DataFrame(rows)
    runs = sorted(held["source_run"].unique())
    boot_rows = []
    for method, group in held.groupby("method"):
        by_run = {run: group[group["source_run"] == run] for run in runs}
        vals = []
        for _ in range(int(cfg["ml"]["bootstrap_samples"])):
            sample_runs = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([by_run[int(r)] for r in sample_runs], ignore_index=True)
            vals.append(summarize_one(sample))
        boot = pd.DataFrame(vals)
        for metric in ["pid_auc", "pid_balanced_accuracy", "calibration_ece", "boundary_migration_rate", "energy_log_area_sigma68", "timing_cfd20_sigma68_ns", "pedestal_transfer_span"]:
            overall.loc[overall["method"].eq(method), f"{metric}_ci_low"] = float(boot[metric].quantile(0.025))
            overall.loc[overall["method"].eq(method), f"{metric}_ci_high"] = float(boot[metric].quantile(0.975))
            boot_rows.append({"method": method, "metric": metric, "ci_low": float(boot[metric].quantile(0.025)), "ci_high": float(boot[metric].quantile(0.975))})
    overall["winner_score"] = (
        (1.0 - overall["pid_balanced_accuracy"])
        + overall["calibration_ece"]
        + overall["boundary_migration_rate"]
        + 0.15 * overall["energy_log_area_sigma68"]
        + 0.005 * overall["timing_cfd20_sigma68_ns"]
        + 0.10 * overall["pedestal_transfer_span"].fillna(0.0)
    )
    overall = overall.sort_values("winner_score").reset_index(drop=True)
    by_run_rows = []
    for (method, run), group in held.groupby(["method", "source_run"]):
        row = {"method": method, "heldout_run": int(run)}
        row.update(summarize_one(group))
        by_run_rows.append(row)
    by_run = pd.DataFrame(by_run_rows).sort_values(["method", "heldout_run"])
    return overall, by_run, pd.DataFrame(boot_rows)


def strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    held["pedestal_band"] = pd.qcut(held["pedestal_memory_adc"], 3, labels=["low", "mid", "high"], duplicates="drop")
    held["energy_band"] = pd.qcut(held["total_area_adc_samples"], 3, labels=["low", "mid", "high"], duplicates="drop")
    held["depth_band"] = pd.qcut(held["depth_mean"], 3, labels=["shallow", "mid", "deep"], duplicates="drop")
    held["late_tail_band"] = pd.qcut(held["late_fraction"], 3, labels=["compact", "nominal", "late"], duplicates="drop")
    rows = []
    for sideband in ["pedestal_band", "energy_band", "depth_band", "late_tail_band", "saturation_mask"]:
        for (method, value), group in held.groupby(["method", sideband], observed=False):
            row = {"sideband": sideband, "value": str(value), "method": method}
            row.update(summarize_one(group))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["sideband", "value", "method"])


def fmt(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def write_report(cfg: dict, out: Path, match: pd.DataFrame, boundary: pd.DataFrame, overall: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, runtime: float) -> None:
    winner = overall.iloc[0]
    trad = overall[overall["method"].eq("bayesian_deltae_template_likelihood")].iloc[0]
    text = f"""# S54c: Bayesian deltaE-E PID Templates Versus Multitask Waveform ML Boundary Stability

## Abstract

Ticket `2477` asks whether a traditional Bayesian deltaE-E/template PID
boundary remains stable against several ML and neural alternatives.  The raw
ROOT reproduction gate is exact: `{int(match.iloc[0]['reproduced'])}` selected
B-stave pulses versus reference `{int(match.iloc[0]['report_value'])}`, delta
`{int(match.iloc[0]['delta'])}`.  The held-out split is by run: train
`{cfg['benchmark_runs']['train']}` and held-out `{cfg['benchmark_runs']['heldout']}`.

The winner named in `result.json` is **`{winner['method']}`** by the declared
boundary-stability score

`S_m = (1 - BAcc_m) + ECE_m + M_m + 0.15 sigma_E,m + 0.005 sigma_t,m + 0.10 P_m`,

where `BAcc` is weak-label balanced accuracy, `ECE` is calibration error, `M` is
boundary migration relative to the frozen deltaE/E-depth label, `sigma_E` is
log-charge residual sigma68, `sigma_t` is CFD timing residual sigma68 in ns, and
`P` is the pedestal-band score span.

## Raw ROOT Reproduction

Raw files are read from `{cfg['raw_root_dir']}`.  For B2/B4/B6/B8 channels
`c`, the pedestal is `b_c = median(x_c[0:4])`, the corrected waveform is
`y_c(t)=x_c(t)-b_c`, and selected B-stave pulses satisfy
`max_t y_c(t) > 1000` ADC.  The reproduction table is:

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Frozen PID Boundary

No event-level external PID truth ROOT was mounted in this worker.  Therefore
S54c is framed as a raw-data weak PID boundary-stability benchmark.  The label is
frozen from train runs only:

`z_i = 1.2 (L_i-q_0.58(L))/sigma_L + 0.9 (D_i-q_0.58(D))/sigma_D - 0.45 (R_i-q_0.42(R))/sigma_R`,

with late/deep label `y_i=1[z_i >= 0]`.  `L` is late charge fraction
`(B6+B8)/(B2+B4+B6+B8)`, `D` is charge-weighted depth, and `R` is upstream
deltaE-over-downstream-energy.  The thresholds are:

{md_table(boundary, ['quantity', 'value'])}

## Methods

The strong traditional method is `bayesian_deltae_template_likelihood`.  It uses
pedestal-subtracted charge integration, CFD timing, depth-weighted deltaE/E
features, and diagonal Gaussian class likelihoods

`log p(z|y) = -1/2 sum_j [(z_j-mu_yj)^2/sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`, and
the new `multitask_waveform_transformer_new`.  The neural models consume the
4x18 B-stack waveform tensor and jointly predict PID boundary score, log-charge
energy proxy, and CFD timing proxy.  All preprocessing, Gaussian moments,
scalers, tree splits, and neural weights are fitted on train runs only.

## Overall Held-Out Results

{md_table(overall, ['method', 'winner_score', 'pid_auc', 'pid_auc_ci_low', 'pid_auc_ci_high', 'pid_balanced_accuracy', 'pid_balanced_accuracy_ci_low', 'pid_balanced_accuracy_ci_high', 'calibration_ece', 'boundary_migration_rate', 'energy_log_area_sigma68', 'timing_cfd20_sigma68_ns', 'pedestal_transfer_span'])}

Relative to the traditional baseline, `{winner['method']}` changes balanced
accuracy by `{fmt(winner['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`,
boundary migration by `{fmt(winner['boundary_migration_rate'] - trad['boundary_migration_rate'])}`,
energy sigma68 by `{fmt(winner['energy_log_area_sigma68'] - trad['energy_log_area_sigma68'])}`,
and timing sigma68 by `{fmt(winner['timing_cfd20_sigma68_ns'] - trad['timing_cfd20_sigma68_ns'])}` ns.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'boundary_migration_rate', 'energy_log_area_sigma68', 'timing_cfd20_sigma68_ns'])}

## Systematic Sidebands

{md_table(strata, ['sideband', 'value', 'method', 'pid_balanced_accuracy', 'boundary_migration_rate', 'calibration_ece', 'energy_log_area_sigma68', 'timing_cfd20_sigma68_ns'])}

## Systematics and Caveats

This is not a particle-truth PID measurement.  It tests stability of a
train-frozen raw deltaE/E-depth boundary under method substitution.  A model can
win the benchmark by reproducing the frozen boundary while still being
unvalidated for physical proton/deuteron classification.  The main systematic is
support leakage through charge and depth, mitigated here by run-held-out splits,
train-only threshold freezing, and pedestal/saturation sideband tables.  The
bootstrap intervals resample held-out runs and therefore cover run-transfer
instability, not the uncertainty of the weak-label definition, detector material
model, or external beam composition.  Saturation is represented by a corrected
peak threshold above 14000 ADC; pile-up sensitivity is approximated by the late
charge tail and cannot replace a two-pulse hand-scan label.

Runtime was `{runtime:.1f}` s on `{platform.platform()}` with git commit
`{git_commit()}`.

## Follow-up Ticket

One novel follow-up was appended: #2480, `S54d: external PID truth join for S54c boundary validation`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    cfg = load_config()
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    claim_text = """claim_helper_command: tn-ticket claim testbeam-laptop-2 --project testbeam
claim_helper_output:
null
# null

null
manual_claim_issue: 2477
manual_claim_command: gh --repo SzeChunYiu/factory-tickets issue edit 2477 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open
manual_claim_evidence: issue #2477 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-2
"""
    (out / "claimed_ticket.txt").write_text(claim_text, encoding="utf-8")

    rng = np.random.default_rng(int(cfg["random_seed"]))
    match = reproduce_counts(cfg)
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    events, waves = read_event_table(cfg)
    events, boundary = freeze_labels(events, out)
    events.to_csv(out / "benchmark_events.csv", index=False)
    np.savez_compressed(out / "benchmark_waveforms.npz", waveforms=waves)

    train = events[events["split"] == "train"].copy()
    preds = [gaussian_likelihood_prediction(train, events)]
    preds.extend(sklearn_predictions(train, events))
    preds.append(neural_prediction("1d_cnn", CNN1D(), train, events, waves, cfg, int(cfg["random_seed"]) + 1))
    preds.append(neural_prediction("multitask_waveform_transformer_new", TinyTransformer(), train, events, waves, cfg, int(cfg["random_seed"]) + 2))
    all_pred = pd.concat(preds, ignore_index=True)
    joined = all_pred.merge(events, on="event_id", how="left", validate="many_to_one")
    joined.to_csv(out / "event_predictions.csv", index=False)

    overall, by_run, boot = summarize(joined, cfg, rng)
    strata = strata_summary(joined)
    overall.to_csv(out / "method_summary.csv", index=False)
    by_run.to_csv(out / "run_heldout_metrics.csv", index=False)
    boot.to_csv(out / "bootstrap_ci.csv", index=False)
    strata.to_csv(out / "sideband_systematics.csv", index=False)
    write_report(cfg, out, match, boundary, overall, by_run, strata, time.time() - started)

    input_rows = []
    for run in configured_runs(cfg):
        path = raw_file(cfg, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size, "role": "raw_bstack_root"})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    winner = overall.iloc[0]
    result = {
        "ticket_id": "2477",
        "project": "testbeam",
        "worker": cfg["worker"],
        "title": cfg["title"],
        "status": "complete",
        "claim_command_run_once": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "manual_claim_after_null_helper": 2477,
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv"
        },
        "split": {"grouping": "source_run", "train_runs": cfg["benchmark_runs"]["train"], "heldout_runs": cfg["benchmark_runs"]["heldout"]},
        "methods": {
            "strong_traditional": "bayesian_deltae_template_likelihood",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "1d_cnn": "1d_cnn",
            "new_architecture": "multitask_waveform_transformer_new"
        },
        "winner": {
            "method": str(winner["method"]),
            "criterion": "minimum held-out boundary-stability score",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_balanced_accuracy": float(winner["pid_balanced_accuracy"]),
            "boundary_migration_rate": float(winner["boundary_migration_rate"]),
            "energy_log_area_sigma68": float(winner["energy_log_area_sigma68"]),
            "timing_cfd20_sigma68_ns": float(winner["timing_cfd20_sigma68_ns"])
        },
        "caveat": "Weak raw deltaE/E-depth PID boundary stability benchmark; not external particle-truth PID.",
        "outputs": {
            "report": "REPORT.md",
            "result": "result.json",
            "method_summary": "method_summary.csv",
            "bootstrap_ci": "bootstrap_ci.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "sideband_systematics": "sideband_systematics.csv",
            "event_predictions": "event_predictions.csv"
        },
        "followup_ticket_appended": {
            "count": 1,
            "issue": 2480,
            "title": "S54d: external PID truth join for S54c boundary validation"
        },
        "git_commit": git_commit(),
        "runtime_seconds": time.time() - started
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": "2477",
        "worker": cfg["worker"],
        "command": f"{sys.executable} scripts/s54c_2477_bayesian_deltae_pid_boundary_stability.py",
        "outputs_sha256": {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"},
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform()
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
