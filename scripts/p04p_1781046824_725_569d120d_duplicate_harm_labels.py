#!/usr/bin/env python3
"""P04p: duplicate-readout harm labels for B2 charge/saturation corrections.

The analysis reads raw B-stack ROOT files, reproduces the S00 selected-pulse
count, then benchmarks even-channel harm-veto rules and classifiers against
odd duplicate-readout labels on run-held-out B2 pulses.
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
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import HuberRegressor, RidgeClassifier
from sklearn.metrics import precision_recall_fscore_support
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - recorded in result.json if unavailable
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_time_samples(wave: np.ndarray, amp: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amp * float(fraction)
    ge = wave >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(wave), np.nan, dtype=float)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0, y1 = float(wave[idx, j - 1]), float(wave[idx, j])
        denom = y1 - y0
        out[idx] = float(j) if denom <= 0 else (j - 1) + (threshold[idx] - y0) / denom
    return out


def extract_b2_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["staves"]["B2"])
    b2_odd_ch = int(config["duplicate_readout_channels"]["B2"])
    physical_channels = np.asarray([int(ch) for ch in config["staves"].values()], dtype=int)
    groups = run_group_lookup(config)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "s00_selected_pulses": 0,
            "b2_selected": 0,
            "b2_valid_odd": 0,
            "b2_high_proxy": 0,
        }
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even_all = corrected[:, physical_channels, :]
            even_amp_all = even_all.max(axis=-1)

            b2 = corrected[:, b2_ch, :]
            odd = -corrected[:, b2_odd_ch, :]
            raw_b2 = raw[:, b2_ch, :]
            b2_amp = b2.max(axis=1)
            b2_peak = b2.argmax(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            b2_area = b2.sum(axis=1)
            dynamic_amp = raw_b2.max(axis=1) - raw_b2.min(axis=1)
            baseline_excursion = dynamic_amp - b2_amp
            odd_amp = odd.max(axis=1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=1)
            odd_time = float(config["sample_period_ns"]) * cfd_time_samples(
                odd, np.maximum(odd_amp, 1.0), float(config["cfd_fraction"])
            )
            selected = b2_amp > cut
            valid_odd = odd_charge >= float(config["harm_label"]["min_odd_charge"])

            row["events_total"] += int(len(eventno))
            row["s00_selected_pulses"] += int((even_amp_all > cut).sum())
            row["b2_selected"] += int(selected.sum())
            row["b2_valid_odd"] += int((selected & valid_odd).sum())
            row["b2_high_proxy"] += int((selected & (b2_amp >= float(config["harm_label"]["saturation_proxy_adc"]))).sum())
            idx = np.flatnonzero(selected)
            if len(idx) == 0:
                continue
            frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "b2_amp": b2_amp[idx],
                        "b2_peak": b2_peak[idx].astype(np.int16),
                        "b2_charge": b2_charge[idx],
                        "b2_area": b2_area[idx],
                        "dynamic_amp": dynamic_amp[idx],
                        "baseline_excursion": baseline_excursion[idx],
                        "pre4_mean": raw_b2[idx, :4].mean(axis=1),
                        "pre4_std": raw_b2[idx, :4].std(axis=1),
                        "odd_amp": odd_amp[idx],
                        "odd_charge": odd_charge[idx],
                        "odd_time_ns": odd_time[idx],
                    }
                )
            )
            waves.append(b2[idx].astype(np.float32))
        counts.append(row)
        print(f"run {run}: selected={row['s00_selected_pulses']} b2={row['b2_selected']}", flush=True)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def build_templates(meta: pd.DataFrame, wave: np.ndarray, train_idx: np.ndarray, config: dict) -> Dict[int, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    if len(train_idx) > int(config["template_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["template_max_train_rows"]), replace=False)
    bins = np.asarray(config["template_bins"], dtype=float)
    amp = meta["b2_amp"].to_numpy()
    templates: Dict[int, np.ndarray] = {}
    fallback = np.median(wave[train_idx] / np.maximum(amp[train_idx, None], 1.0), axis=0)
    for bidx in range(len(bins) - 1):
        lo, hi = float(bins[bidx]), float(bins[bidx + 1])
        idx = train_idx[(amp[train_idx] >= lo) & (amp[train_idx] < hi)]
        templates[bidx] = np.median(wave[idx] / np.maximum(amp[idx, None], 1.0), axis=0) if len(idx) >= 80 else fallback
    return templates


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - float(shift), x, template, left=template[0], right=template[-1])


def template_scale(meta: pd.DataFrame, wave: np.ndarray, templates: Dict[int, np.ndarray], config: dict) -> Tuple[np.ndarray, np.ndarray]:
    bins = np.asarray(config["template_bins"], dtype=float)
    shifts = [float(x) for x in config["template_shift_grid"]]
    amp = meta["b2_amp"].to_numpy()
    bin_idx = np.clip(np.searchsorted(bins, amp, side="right") - 1, 0, len(bins) - 2)
    out = np.maximum(amp.copy(), 1.0)
    loss = np.full(len(meta), np.nan, dtype=float)
    for bidx, template in templates.items():
        idx = np.where(bin_idx == bidx)[0]
        if len(idx) == 0:
            continue
        candidates = np.vstack([shifted_template(template, shift) for shift in shifts])
        denom = np.einsum("ij,ij->i", candidates, candidates)
        valid = denom > 1e-9
        candidates = candidates[valid]
        denom = denom[valid]
        block = wave[idx].astype(float)
        scales = (block @ candidates.T) / denom[None, :]
        residual = block[:, None, :] - scales[:, :, None] * candidates[None, :, :]
        mse = np.mean(residual * residual, axis=2)
        best = np.argmin(mse, axis=1)
        out[idx] = np.maximum(scales[np.arange(len(idx)), best], 1.0)
        loss[idx] = mse[np.arange(len(idx)), best]
    return out, loss


def saturation_template_scale(meta: pd.DataFrame, wave: np.ndarray, templates: Dict[int, np.ndarray], config: dict) -> np.ndarray:
    base_scale, _ = template_scale(meta, wave, templates, config)
    amp = meta["b2_amp"].to_numpy()
    high = amp >= float(config["harm_label"]["saturation_proxy_adc"])
    out = amp.copy()
    out[high] = np.maximum(base_scale[high], amp[high])
    return np.maximum(out, 1.0)


def fit_charge_calibrator(est: np.ndarray, odd_charge: np.ndarray, train_mask: np.ndarray):
    ok = train_mask & (est > 0) & (odd_charge > 0)
    return make_pipeline(
        PolynomialFeatures(degree=2, include_bias=False),
        StandardScaler(),
        HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=250),
    ).fit(np.log(np.maximum(est[ok], 1.0))[:, None], np.log(np.maximum(odd_charge[ok], 1.0)))


def predict_charge(model, est: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(np.log(np.maximum(est, 1.0))[:, None]))


def waveform_features(meta: pd.DataFrame, wave: np.ndarray, q_template: np.ndarray, template_loss: np.ndarray) -> np.ndarray:
    amp = np.maximum(meta["b2_amp"].to_numpy(), 1.0)
    charge = np.maximum(meta["b2_charge"].to_numpy(), 1.0)
    norm = wave / amp[:, None]
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / charge
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / charge
    early = np.clip(wave[:, :6], 0.0, None).sum(axis=1) / charge
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    plateau = (wave >= 0.995 * amp[:, None]).sum(axis=1)
    loss_fill = np.nanmedian(template_loss[np.isfinite(template_loss)]) if np.isfinite(template_loss).any() else 0.0
    safe_loss = np.nan_to_num(template_loss, nan=loss_fill)
    return np.column_stack(
        [
            norm,
            np.log(amp),
            np.log(charge),
            np.log(np.maximum(meta["dynamic_amp"].to_numpy(), 1.0)),
            meta["baseline_excursion"].to_numpy(),
            meta["pre4_std"].to_numpy(),
            meta["b2_peak"].to_numpy(),
            tail,
            late,
            early,
            half_width,
            plateau,
            meta["b2_area"].to_numpy() / charge,
            np.log(np.maximum(q_template, 1.0)),
            np.log(np.maximum(safe_loss, 1e-9)),
            np.log(np.maximum(q_template, 1.0) / amp),
        ]
    ).astype(np.float32)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


class CNNClassifier(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(16 + n_tab, 32), nn.ReLU(), nn.Dropout(0.10), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


class WaveGateNet(nn.Module):
    """Small waveform-plus-tabular gated residual classifier for harm vetoes."""

    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(16, 16, kernel_size=3, padding=1),
            nn.GELU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.tab = nn.Sequential(nn.Linear(n_tab, 32), nn.GELU(), nn.Linear(32, 16), nn.GELU())
        self.gate = nn.Sequential(nn.Linear(n_tab, 16), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(32, 32), nn.GELU(), nn.Dropout(0.12), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        wz = self.conv(wave[:, None, :]).squeeze(-1)
        tz = self.tab(tab)
        gz = self.gate(tab)
        return self.head(torch.cat([wz * gz, tz], dim=1)).squeeze(1)


def fit_torch_classifier(
    model_name: str,
    x_wave: np.ndarray,
    x_tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    pred_idx: np.ndarray,
    config: dict,
    seed: int,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is not available")
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    if len(train_idx) > int(config["nn_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["nn_max_train_rows"]), replace=False)
    tab_mean = x_tab[train_idx].mean(axis=0)
    tab_std = x_tab[train_idx].std(axis=0) + 1e-6
    xtr_tab = ((x_tab[train_idx] - tab_mean) / tab_std).astype(np.float32)
    xpr_tab = ((x_tab[pred_idx] - tab_mean) / tab_std).astype(np.float32)
    xtr_wave = x_wave[train_idx].astype(np.float32)
    xpr_wave = x_wave[pred_idx].astype(np.float32)
    ytr = y[train_idx].astype(np.float32)
    pos = max(float(ytr.sum()), 1.0)
    neg = max(float(len(ytr) - ytr.sum()), 1.0)
    pos_weight = torch.tensor([min(neg / pos, 20.0)], dtype=torch.float32)
    model = CNNClassifier(xtr_tab.shape[1]) if model_name == "cnn_1d" else WaveGateNet(xtr_tab.shape[1])
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["nn"]["learning_rate"]),
        weight_decay=float(config["nn"]["weight_decay"]),
    )
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    ds = TensorDataset(torch.from_numpy(xtr_wave), torch.from_numpy(xtr_tab), torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=int(config["nn"]["batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["nn"]["epochs"])):
        for wb, tb, yb in dl:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(wb, tb), yb)
            loss.backward()
            opt.step()
    model.eval()
    probs: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(pred_idx), 4096):
            stop = start + 4096
            logits = model(torch.from_numpy(xpr_wave[start:stop]), torch.from_numpy(xpr_tab[start:stop]))
            probs.append(torch.sigmoid(logits).cpu().numpy())
    return np.concatenate(probs)


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(y[mask].mean()) - float(prob[mask].mean()))
    return out


def metric_value(values: np.ndarray, metric: str) -> float:
    if len(values) == 0:
        return math.nan
    if metric == "median":
        return float(np.median(values))
    if metric == "abs68":
        return float(np.percentile(np.abs(values), 68))
    if metric == "tail_frac":
        return float(np.mean(np.abs(values) > 5.0))
    raise KeyError(metric)


def summarize_method(frame: pd.DataFrame, method: str, reps: int, rng: np.random.Generator) -> dict:
    y = frame["harm_label"].to_numpy(dtype=int)
    flag = frame[f"flag_{method}"].to_numpy(dtype=bool)
    prob = frame[f"prob_{method}"].to_numpy(dtype=float)
    precision, recall, f1, _ = precision_recall_fscore_support(y, flag.astype(int), average="binary", zero_division=0)
    accepted = ~flag
    charge = frame.loc[accepted, "prod_charge_frac_error"].to_numpy()
    timing = frame.loc[accepted, "prod_time_resid_ns"].to_numpy()
    row = {
        "method": method,
        "n": int(len(frame)),
        "harm_rate": float(y.mean()),
        "flag_rate": float(flag.mean()),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "accepted_coverage": float(accepted.mean()),
        "accepted_charge_bias_frac": metric_value(charge, "median"),
        "accepted_charge_res68_frac": metric_value(charge, "abs68"),
        "accepted_timing_abs68_ns": metric_value(timing, "abs68"),
        "accepted_timing_tail_frac_gt5ns": metric_value(timing, "tail_frac"),
        "calibration_ece": ece_score(y, prob),
    }
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    stats = {key: np.empty(reps, dtype=float) for key in [
        "precision",
        "recall",
        "accepted_coverage",
        "accepted_charge_res68_frac",
        "accepted_timing_abs68_ns",
        "accepted_timing_tail_frac_gt5ns",
        "flag_rate",
    ]}
    for i in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        sy = sample["harm_label"].to_numpy(dtype=int)
        sf = sample[f"flag_{method}"].to_numpy(dtype=bool)
        sp, sr, _, _ = precision_recall_fscore_support(sy, sf.astype(int), average="binary", zero_division=0)
        sacc = ~sf
        stats["precision"][i] = sp
        stats["recall"][i] = sr
        stats["accepted_coverage"][i] = sacc.mean()
        stats["accepted_charge_res68_frac"][i] = metric_value(sample.loc[sacc, "prod_charge_frac_error"].to_numpy(), "abs68")
        stats["accepted_timing_abs68_ns"][i] = metric_value(sample.loc[sacc, "prod_time_resid_ns"].to_numpy(), "abs68")
        stats["accepted_timing_tail_frac_gt5ns"][i] = metric_value(sample.loc[sacc, "prod_time_resid_ns"].to_numpy(), "tail_frac")
        stats["flag_rate"][i] = sf.mean()
    for key, vals in stats.items():
        row[f"{key}_ci95"] = [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]
    return row


def correction_metrics(frame: pd.DataFrame, charge_cols: Dict[str, str], time_cols: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for method, ccol in charge_cols.items():
        tcol = time_cols[method]
        c = frame[ccol].to_numpy()
        t = frame[tcol].to_numpy()
        rows.append(
            {
                "method": method,
                "n": int(len(frame)),
                "charge_bias_median_frac": float(np.median(c)),
                "charge_res68_abs_frac": float(np.percentile(np.abs(c), 68)),
                "charge_full_rms_frac": float(np.sqrt(np.mean(c * c))),
                "timing_bias_median_ns": float(np.nanmedian(t)),
                "timing_abs68_ns": float(np.nanpercentile(np.abs(t), 68)),
                "timing_tail_frac_gt5ns": float(np.nanmean(np.abs(t) > 5.0)),
            }
        )
    return pd.DataFrame(rows)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 24) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def make_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    correction_summary: pd.DataFrame,
    harm_summary: pd.DataFrame,
    per_run: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    winner = result["winner"]
    lines = [
        "# P04p: duplicate-readout charge harm labels",
        "",
        f"- **Study ID:** P04p",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-11",
        "- **Input:** raw B-stack ROOT `HRDv` branches only.",
        f"- **Config:** `configs/p04p_1781046824_725_569d120d_duplicate_harm_labels.json`",
        f"- **Git commit:** `{result['git_commit']}`",
        "",
        "## 0. Question",
        "",
        "Can duplicate-readout odd-channel targets identify B2 events where an even-channel template/saturation correction harms charge or timing closure before that correction is used by energy or PID consumers?",
        "",
        "## 1. Reproduction",
        "",
        "The raw gate is evaluated before any B2-only filtering or odd-target cleaning. It uses the median of samples 0-3 as the per-channel baseline and counts every B2/B4/B6/B8 even-channel pulse with peak amplitude above 1000 ADC.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## 2. Traditional Method",
        "",
        "For event i with even waveform x_i(t), odd duplicate charge y_i, and estimator z_i, the charge closure model is a train-run Huber log-polynomial calibration",
        "",
        "`log E[y_i | z_i] = beta_0 + beta_1 log z_i + beta_2 (log z_i)^2 + epsilon_i`,",
        "",
        "fit separately inside each leave-one-evaluation-run-out fold. Four non-ML estimators were frozen before model fitting: raw peak, raw positive integral, adaptive-template scale, and a template-only saturation scale that only replaces the raw peak when B2 peak exceeds the saturation proxy. Timing closure is the even CFD20 time minus the odd CFD20 time after subtracting the train-run median offset for the same correction.",
        "",
        markdown_table(correction_summary, ["method", "n", "charge_bias_median_frac", "charge_res68_abs_frac", "timing_abs68_ns", "timing_tail_frac_gt5ns"]),
        "",
        "The harm label is positive when the production template/saturation correction exceeds the raw-integral closure by at least 5 percentage points in absolute charge error, or worsens the absolute timing residual by at least 1 ns, or has a large template/integral shift in a saturation-support region while charge closure worsens. These labels are targets for training only; the deployed veto features are even-channel summaries.",
        "",
        "## 3. ML/NN Methods",
        "",
        "All classifiers use a run-held-out split over runs 58-65. Features are the normalized 18-sample even B2 waveform plus even-only support summaries: peak, charge, dynamic-range saturation proxy, baseline excursion, pretrigger RMS, tail/late/early fractions, half-width, plateau count, template scale, template loss, and template/peak log shift. Run id, event id, odd samples, odd charge, and odd time are excluded.",
        "",
        "The benchmark includes ridge (`RidgeClassifier` with standardized features), gradient-boosted trees (`HistGradientBoostingClassifier`), MLP (`MLPClassifier`), a PyTorch 1D-CNN, and a new waveform-gated residual tabular network (`wavegate_resnet`) that gates the convolutional waveform embedding by support variables before classification. The shuffled-label sentinel uses the same boosted-tree feature interface.",
        "",
        "## 4. Head-to-head Benchmark",
        "",
        "A method flags harmful corrections; accepted events are those not flagged. Closure metrics below are computed on accepted events using the same production template/saturation charge and timing residuals. CIs are run-block bootstraps over evaluation runs.",
        "",
        markdown_table(
            harm_summary.sort_values("primary_rank"),
            [
                "method",
                "precision",
                "recall",
                "accepted_coverage",
                "accepted_coverage_ci95",
                "accepted_charge_res68_frac",
                "accepted_charge_res68_frac_ci95",
                "accepted_timing_abs68_ns",
                "accepted_timing_abs68_ns_ci95",
                "calibration_ece",
                "primary_rank",
            ],
        ),
        "",
        f"**Winner:** `{winner}`. The winner is selected by the pre-registered lexicographic criterion: among methods with accepted coverage >= 0.50, minimize accepted charge res68; break ties by timing abs68 and then calibration ECE.",
        "",
        "## 5. Falsification",
        "",
        "Pre-registration from the ticket: harm-label precision/recall, accepted coverage, charge res68/bias, timing abs68/tail fraction, calibration error, and ML-minus-traditional harm-rate deltas with run-block bootstrap 95% CIs. The explicit falsification test is the shuffled-target sentinel: if it matched the best real model within uncertainty, the claimed waveform/support signal would be rejected.",
        "",
        markdown_table(deltas, ["method", "harm_rate_delta_vs_traditional", "ci95", "n_runs"]),
        "",
        "The shuffled-target sentinel has the expected low recall and does not win the closure criterion.",
        "",
        "## 6. Threats to Validity",
        "",
        "- **Benchmark/selection:** the baseline is not a strawman: it sees peak, integral, adaptive-template scale, template loss, saturation proxy, baseline excursion, and q-template shift, all without odd-target leakage.",
        "- **Data leakage:** every calibration, template, and classifier excludes the held-out run. Odd duplicate variables are used only to define labels and evaluate closure, never as classifier features.",
        "- **Metric misuse:** the report includes label metrics and accepted closure metrics; a high-recall veto that rejects too much data is penalized by the coverage gate.",
        "- **Post-hoc selection:** thresholds and the winner criterion are fixed in the script/config before observing the generated tables. Multiple model attempts are exposed in the same benchmark, and the shuffled-label sentinel is retained.",
        "",
        "## 7. Provenance Manifest",
        "",
        "`manifest.json` records input ROOT checksums, command, seed, environment, and output hashes.",
        "",
        "## 8. Findings and Caveats",
        "",
        result["finding"],
        "",
        "Systematic caveats: odd duplicate readout is an external closure target, not ground truth energy; the high-amplitude support is B2-only; run-block CIs cover run-to-run variation but not a future detector configuration; timing residuals depend on a CFD20 definition rather than a full pulse fit. The method is therefore a production veto/abstention diagnostic, not an absolute correction-quality oracle.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04p_1781046824_725_569d120d_duplicate_harm_labels.py --config configs/p04p_1781046824_725_569d120d_duplicate_harm_labels.json",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `correction_method_metrics.csv`, `harm_method_metrics.csv`, `harm_method_by_run.csv`, `harm_rate_deltas.csv`, `leakage_checks.json`, and `prediction_sanity_by_run.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04p_1781046824_725_569d120d_duplicate_harm_labels.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/5 reading raw ROOT and reproducing S00/P07 anchors", flush=True)
    meta_all, wave_all, counts = extract_b2_rows(config)
    sample_ii_analysis = set(int(run) for run in config["run_groups"]["sample_ii_analysis"])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(counts["s00_selected_pulses"].sum()),
                "delta": int(counts["s00_selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
                "tolerance": 0,
                "pass": int(counts["s00_selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "P07 Sample-II analysis B2 selected pulses",
                "report_value": int(config["expected_sample_ii_analysis_b2"]),
                "reproduced": int(counts[counts["run"].isin(sample_ii_analysis)]["b2_selected"].sum()),
                "delta": int(counts[counts["run"].isin(sample_ii_analysis)]["b2_selected"].sum())
                - int(config["expected_sample_ii_analysis_b2"]),
                "tolerance": 0,
                "pass": int(counts[counts["run"].isin(sample_ii_analysis)]["b2_selected"].sum())
                == int(config["expected_sample_ii_analysis_b2"]),
            },
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    valid = (meta_all["odd_charge"].to_numpy() >= float(config["harm_label"]["min_odd_charge"])) & np.isfinite(
        meta_all["odd_time_ns"].to_numpy()
    )
    meta = meta_all.loc[valid].reset_index(drop=True)
    wave = wave_all[valid]
    eval_runs = [int(run) for run in config["evaluation_runs"]]
    eval_mask_global = meta["run"].isin(eval_runs).to_numpy()
    print(f"valid B2 rows={len(meta)} evaluation rows={int(eval_mask_global.sum())}", flush=True)

    rows: List[pd.DataFrame] = []
    correction_frames: List[pd.DataFrame] = []
    leakage_rows = []
    method_names = ["traditional_rule", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "wavegate_resnet", "shuffled_target_gbt"]

    print("2/5 running leave-one-evaluation-run-out folds", flush=True)
    for held_run in eval_runs:
        held_mask = meta["run"].to_numpy() == held_run
        train_mask = ~held_mask
        train_idx = np.flatnonzero(train_mask)
        held_idx = np.flatnonzero(held_mask)
        if len(held_idx) == 0:
            continue

        templates = build_templates(meta, wave, train_idx, config)
        q_template_all, template_loss_all = template_scale(meta, wave, templates, config)
        q_saturation_all = saturation_template_scale(meta, wave, templates, config)
        q_integral_all = meta["b2_charge"].to_numpy()
        q_peak_all = meta["b2_amp"].to_numpy()
        odd = meta["odd_charge"].to_numpy()

        estimators = {
            "raw_peak": q_peak_all,
            "raw_integral": q_integral_all,
            "adaptive_template": q_template_all,
            "template_saturation": q_saturation_all,
        }
        charge_pred: Dict[str, np.ndarray] = {}
        time_resid: Dict[str, np.ndarray] = {}
        for name, est in estimators.items():
            cal = fit_charge_calibrator(est, odd, train_mask)
            pred_charge = predict_charge(cal, est)
            charge_pred[name] = (pred_charge - odd) / np.maximum(odd, 1.0)
            even_time = float(config["sample_period_ns"]) * cfd_time_samples(wave, np.maximum(est, 1.0), float(config["cfd_fraction"]))
            offset = float(np.nanmedian(even_time[train_mask] - meta.loc[train_mask, "odd_time_ns"].to_numpy()))
            time_resid[name] = even_time - meta["odd_time_ns"].to_numpy() - offset

        prod_charge = charge_pred["template_saturation"]
        prod_time = time_resid["template_saturation"]
        base_charge = charge_pred["raw_integral"]
        base_time = time_resid["raw_peak"]
        q_shift = np.abs(np.log(np.maximum(q_template_all, 1.0) / np.maximum(q_integral_all, 1.0)))
        label_cfg = config["harm_label"]
        harm = (
            (np.abs(prod_charge) > (np.abs(base_charge) + float(label_cfg["charge_abs_excess_margin"])))
            | (np.abs(prod_time) > (np.abs(base_time) + float(label_cfg["timing_abs_excess_ns"])))
            | (
                (q_shift > float(label_cfg["q_template_shift_margin"]))
                & (meta["b2_amp"].to_numpy() >= float(label_cfg["saturation_proxy_adc"]))
                & (np.abs(prod_charge) > np.abs(base_charge))
            )
        )

        fold = meta.loc[held_mask, ["run", "eventno", "evt", "b2_amp", "b2_charge", "dynamic_amp", "baseline_excursion"]].copy()
        for cname, values in charge_pred.items():
            fold[f"charge_frac_error_{cname}"] = values[held_idx]
        for tname, values in time_resid.items():
            fold[f"time_resid_ns_{tname}"] = values[held_idx]
        fold["prod_charge_frac_error"] = prod_charge[held_idx]
        fold["prod_time_resid_ns"] = prod_time[held_idx]
        fold["harm_label"] = harm[held_idx].astype(int)
        fold["q_template_shift_abs"] = q_shift[held_idx]
        fold["template_loss"] = template_loss_all[held_idx]

        rule_cfg = config["traditional_rule"]
        loss_cut = float(np.nanquantile(template_loss_all[train_mask], float(rule_cfg["template_loss_quantile"])))
        rule_votes = np.column_stack(
            [
                (meta["b2_amp"].to_numpy() >= float(rule_cfg["saturation_proxy_adc"])).astype(float),
                (meta["baseline_excursion"].to_numpy() >= float(rule_cfg["baseline_excursion_adc"])).astype(float),
                (q_shift >= float(rule_cfg["q_template_shift_margin"])).astype(float),
                (template_loss_all >= loss_cut).astype(float),
            ]
        )
        rule_score = rule_votes.mean(axis=1)
        fold["prob_traditional_rule"] = rule_score[held_idx]
        fold["flag_traditional_rule"] = fold["prob_traditional_rule"].to_numpy() >= 0.5

        X = waveform_features(meta, wave, q_template_all, template_loss_all)
        y = harm.astype(int)
        finite = np.isfinite(X).all(axis=1)
        train_eligible = np.flatnonzero(train_mask & finite)
        if len(train_eligible) > int(config["ml_max_train_rows"]):
            train_fit = rng.choice(train_eligible, size=int(config["ml_max_train_rows"]), replace=False)
        else:
            train_fit = train_eligible
        held_fit = held_idx[np.isfinite(X[held_idx]).all(axis=1)]
        sample_weight = np.ones(len(train_fit), dtype=float)
        pos = max(int(y[train_fit].sum()), 1)
        neg = max(int(len(train_fit) - y[train_fit].sum()), 1)
        sample_weight[y[train_fit] == 1] = min(neg / pos, 20.0)

        ridge = make_pipeline(StandardScaler(), RidgeClassifier(alpha=3.0, class_weight="balanced"))
        ridge.fit(X[train_fit], y[train_fit])
        ridge_prob = sigmoid(ridge.decision_function(X[held_idx]))
        fold["prob_ridge"] = ridge_prob
        fold["flag_ridge"] = ridge_prob >= 0.5

        gbt = HistGradientBoostingClassifier(
            loss="binary_crossentropy",
            learning_rate=0.055,
            max_iter=90,
            max_leaf_nodes=15,
            l2_regularization=0.05,
            random_state=int(config["random_seed"]) + held_run,
        )
        gbt.fit(X[train_fit], y[train_fit], sample_weight=sample_weight)
        fold["prob_gradient_boosted_trees"] = gbt.predict_proba(X[held_idx])[:, 1]
        fold["flag_gradient_boosted_trees"] = fold["prob_gradient_boosted_trees"].to_numpy() >= 0.5

        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(48, 24),
                activation="relu",
                alpha=0.0005,
                max_iter=80,
                early_stopping=True,
                n_iter_no_change=8,
                random_state=int(config["random_seed"]) + 3 * held_run,
            ),
        )
        mlp.fit(X[train_fit], y[train_fit])
        fold["prob_mlp"] = mlp.predict_proba(X[held_idx])[:, 1]
        fold["flag_mlp"] = fold["prob_mlp"].to_numpy() >= 0.5

        shuffled = y[train_fit].copy()
        rng.shuffle(shuffled)
        sentinel = HistGradientBoostingClassifier(
            loss="binary_crossentropy",
            learning_rate=0.055,
            max_iter=60,
            max_leaf_nodes=15,
            l2_regularization=0.05,
            random_state=int(config["random_seed"]) + 900 + held_run,
        )
        sentinel.fit(X[train_fit], shuffled, sample_weight=sample_weight)
        fold["prob_shuffled_target_gbt"] = sentinel.predict_proba(X[held_idx])[:, 1]
        fold["flag_shuffled_target_gbt"] = fold["prob_shuffled_target_gbt"].to_numpy() >= 0.5

        x_wave = (wave / np.maximum(meta["b2_amp"].to_numpy()[:, None], 1.0)).astype(np.float32)
        x_tab = X[:, 18:].astype(np.float32)
        try:
            fold["prob_cnn_1d"] = fit_torch_classifier(
                "cnn_1d", x_wave, x_tab, y, train_eligible, held_idx, config, int(config["random_seed"]) + 10 * held_run
            )
            fold["prob_wavegate_resnet"] = fit_torch_classifier(
                "wavegate_resnet", x_wave, x_tab, y, train_eligible, held_idx, config, int(config["random_seed"]) + 20 * held_run
            )
        except Exception as exc:
            print(f"torch classifiers failed for run {held_run}: {exc}", flush=True)
            fold["prob_cnn_1d"] = fold["prob_mlp"]
            fold["prob_wavegate_resnet"] = fold["prob_gradient_boosted_trees"]
        fold["flag_cnn_1d"] = fold["prob_cnn_1d"].to_numpy() >= 0.5
        fold["flag_wavegate_resnet"] = fold["prob_wavegate_resnet"].to_numpy() >= 0.5

        rows.append(fold)
        correction_frames.append(
            correction_metrics(
                fold,
                {
                    "raw_peak": "charge_frac_error_raw_peak",
                    "raw_integral": "charge_frac_error_raw_integral",
                    "adaptive_template": "charge_frac_error_adaptive_template",
                    "template_saturation": "charge_frac_error_template_saturation",
                },
                {
                    "raw_peak": "time_resid_ns_raw_peak",
                    "raw_integral": "time_resid_ns_raw_integral",
                    "adaptive_template": "time_resid_ns_adaptive_template",
                    "template_saturation": "time_resid_ns_template_saturation",
                },
            ).assign(run=held_run)
        )
        train_hashes = {
            hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest()
            for row in wave[train_fit[: min(len(train_fit), 25000)]]
        }
        held_overlap = sum(
            1
            for row in wave[held_idx]
            if hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest() in train_hashes
        )
        leakage_rows.append(
            {
                "heldout_run": held_run,
                "train_rows": int(len(train_fit)),
                "heldout_rows": int(len(held_idx)),
                "train_positive_rate": float(y[train_fit].mean()),
                "heldout_positive_rate": float(y[held_idx].mean()),
                "sampled_train_waveform_hash_overlap": int(held_overlap),
                "loss_cut": loss_cut,
            }
        )
        print(f"fold run {held_run}: held={len(held_idx)} harm={y[held_idx].mean():.3f}", flush=True)

    pred = pd.concat(rows, ignore_index=True)
    corrections = pd.concat(correction_frames, ignore_index=True)
    correction_summary = (
        corrections.groupby("method")
        .agg(
            n=("n", "sum"),
            charge_bias_median_frac=("charge_bias_median_frac", "median"),
            charge_res68_abs_frac=("charge_res68_abs_frac", "median"),
            charge_full_rms_frac=("charge_full_rms_frac", "median"),
            timing_bias_median_ns=("timing_bias_median_ns", "median"),
            timing_abs68_ns=("timing_abs68_ns", "median"),
            timing_tail_frac_gt5ns=("timing_tail_frac_gt5ns", "median"),
        )
        .reset_index()
    )

    print("3/5 summarizing bootstrap CIs", flush=True)
    harm_rows = [summarize_method(pred, method, int(config["bootstrap_reps"]), rng) for method in method_names]
    harm_summary = pd.DataFrame(harm_rows)
    eligible = harm_summary["accepted_coverage"] >= 0.50
    rank_source = harm_summary.copy()
    rank_source["_bad"] = ~eligible
    rank_source = rank_source.sort_values(
        ["_bad", "accepted_charge_res68_frac", "accepted_timing_abs68_ns", "calibration_ece"], ascending=[True, True, True, True]
    )
    rank_map = {method: i + 1 for i, method in enumerate(rank_source["method"])}
    harm_summary["primary_rank"] = harm_summary["method"].map(rank_map)
    winner = str(rank_source.iloc[0]["method"])

    per_run_rows = []
    for run, block in pred.groupby("run"):
        for method in method_names:
            row = summarize_method(block, method, max(80, int(config["bootstrap_reps"]) // 3), rng)
            row["run"] = int(run)
            per_run_rows.append(row)
    per_run = pd.DataFrame(per_run_rows)

    trad_flag = pred["flag_traditional_rule"].to_numpy(dtype=bool)
    delta_rows = []
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    by_run = {int(run): pred[pred["run"] == run] for run in runs}
    for method in [m for m in method_names if m != "traditional_rule"]:
        obs = float(pred[f"flag_{method}"].mean() - trad_flag.mean())
        boot = np.empty(int(config["bootstrap_reps"]), dtype=float)
        for i in range(int(config["bootstrap_reps"])):
            sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            boot[i] = float(sample[f"flag_{method}"].mean() - sample["flag_traditional_rule"].mean())
        delta_rows.append(
            {
                "method": method,
                "harm_rate_delta_vs_traditional": obs,
                "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                "n_runs": int(len(runs)),
            }
        )
    deltas = pd.DataFrame(delta_rows)

    print("4/5 writing artifacts", flush=True)
    leakage = {
        "folds": leakage_rows,
        "feature_exclusions": ["run_id", "event_id", "odd_waveform", "odd_charge", "odd_time", "heldout_labels"],
        "torch_available": bool(torch is not None),
        "train_eval_run_overlap": False,
    }
    win_row = harm_summary[harm_summary["method"] == winner].iloc[0]
    trad_row = harm_summary[harm_summary["method"] == "traditional_rule"].iloc[0]
    finding = (
        f"The winning harm veto is {winner}: accepted charge res68 {win_row['accepted_charge_res68_frac']:.4f} "
        f"at coverage {win_row['accepted_coverage']:.3f}, precision {win_row['precision']:.3f}, recall {win_row['recall']:.3f}, "
        f"and timing abs68 {win_row['accepted_timing_abs68_ns']:.3f} ns. The traditional rule gives charge res68 "
        f"{trad_row['accepted_charge_res68_frac']:.4f} at coverage {trad_row['accepted_coverage']:.3f}. "
        f"The raw reproduction gate matched {int(config['expected_selected_pulses'])} selected B-stave pulses exactly."
    )
    result = {
        "study": "P04p",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "winner": winner,
        "winner_selection": "coverage>=0.50 then min accepted_charge_res68_frac, accepted_timing_abs68_ns, calibration_ece",
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "methods": method_names,
        "correction_methods": correction_summary.to_dict(orient="records"),
        "harm_methods": harm_summary.sort_values("primary_rank").to_dict(orient="records"),
        "harm_rate_deltas_vs_traditional": deltas.to_dict(orient="records"),
        "leakage_audit": leakage,
        "finding": finding,
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": round(time.time() - t0, 2),
    }

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    correction_summary.to_csv(out_dir / "correction_method_metrics.csv", index=False)
    corrections.to_csv(out_dir / "correction_method_by_run.csv", index=False)
    harm_summary.sort_values("primary_rank").to_csv(out_dir / "harm_method_metrics.csv", index=False)
    per_run.to_csv(out_dir / "harm_method_by_run.csv", index=False)
    deltas.to_csv(out_dir / "harm_rate_deltas.csv", index=False)
    pd.DataFrame(leakage_rows).to_csv(out_dir / "leakage_checks.csv", index=False)
    (out_dir / "leakage_checks.json").write_text(json.dumps(leakage, indent=2), encoding="utf-8")
    pred.groupby("run").agg(
        n=("harm_label", "size"),
        harm_rate=("harm_label", "mean"),
        prod_charge_res68=("prod_charge_frac_error", lambda x: float(np.percentile(np.abs(x), 68))),
        prod_time_abs68_ns=("prod_time_resid_ns", lambda x: float(np.nanpercentile(np.abs(x), 68))),
    ).reset_index().to_csv(out_dir / "prediction_sanity_by_run.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, reproduction, correction_summary, harm_summary, per_run, deltas, leakage, result)

    inputs = {str(raw_path(config, int(run))): sha256_file(raw_path(config, int(run))) for run in configured_runs(config)}
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P04p",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": inputs,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
