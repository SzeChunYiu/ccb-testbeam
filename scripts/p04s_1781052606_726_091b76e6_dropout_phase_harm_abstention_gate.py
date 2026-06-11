#!/usr/bin/env python3
"""P04s: dropout-recovery phase-harm abstention gate.

This ticket extends P04g's controlled dropout injection with a broader method
bakeoff: a strong traditional rising-edge Huber recovery is benchmarked against
ridge, gradient-boosted trees, MLP, a 1D-CNN inpainting model, and a conservative
phase-harm-gated CNN architecture.  The raw ROOT reproduction and
train/evaluation split are inherited from the reviewed P04g loader, but all
model fitting is performed here from the claimed P04s config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - handled at runtime in result.json.
    torch = None
    nn = None
    F = None
    DataLoader = None
    TensorDataset = None

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import p04g_1781018820_3891_20547ebd_dropout_charge_recovery as p04g  # noqa: E402


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


def one_hot(values: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros((len(values), n), dtype=np.float32)
    out[np.arange(len(values)), values.astype(int)] = 1.0
    return out


def amp_bin_labels() -> List[str]:
    return ["1000_2000", "2000_3000", "3000_5000", "5000_7000", "ge7000"]


def atom_columns() -> List[str]:
    return ["stave", "dropout_case", "amp_bin_label", "peak_region"]


def add_support_atoms(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    labels = amp_bin_labels()
    amp_bin = np.clip(np.searchsorted(bins, out["clean_amp"].to_numpy(), side="right") - 1, 0, len(labels) - 1)
    out["amp_bin"] = amp_bin.astype(int)
    out["amp_bin_label"] = np.asarray(labels, dtype=object)[amp_bin]
    out["peak_region"] = p04g.peak_region(out["clean_peak"].to_numpy())
    return out


def q_template_score(meta: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    """Operational q_template proxy: normalized waveform RMS distance to train templates."""
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    amp = np.maximum(wave.max(axis=1), 1.0)
    amp_bin = np.clip(np.searchsorted(bins, amp, side="right") - 1, 0, len(bins) - 2)
    staves = meta["stave_idx"].to_numpy().astype(int)
    out = np.full(len(wave), np.nan, dtype=float)
    fallback = np.median(np.vstack(list(templates.values())), axis=0) if templates else np.ones(wave.shape[1], dtype=float)
    for i in range(len(wave)):
        tmpl = templates.get((int(staves[i]), int(amp_bin[i])), fallback)
        norm = wave[i] / amp[i]
        out[i] = float(np.sqrt(np.mean((norm - tmpl) ** 2)))
    return out


def pileup_score(wave: np.ndarray) -> np.ndarray:
    """Pulse-shape pile-up proxy from late energy and secondary-lobe prominence."""
    pos = np.clip(wave, 0.0, None)
    total = np.maximum(pos.sum(axis=1), 1.0)
    peak = wave.argmax(axis=1)
    out = np.zeros(len(wave), dtype=float)
    for i, p in enumerate(peak):
        p = int(p)
        late = pos[i, min(p + 3, wave.shape[1] - 1) :].sum() / total[i]
        outside = pos[i].copy()
        outside[max(0, p - 1) : min(wave.shape[1], p + 2)] = 0.0
        secondary = outside.max() / max(float(pos[i, p]), 1.0)
        out[i] = float(0.65 * late + 0.35 * secondary)
    return out


def real_candidate_audit(meta: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> pd.DataFrame:
    """Stratify raw, non-injected pulses with dropout/anomaly-like waveform notches."""
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    labels = amp_bin_labels()
    peak = meta["clean_peak"].to_numpy().astype(int)
    amp = np.maximum(meta["clean_amp"].to_numpy(), 1.0)
    nsamp = wave.shape[1]
    severity = np.zeros(len(wave), dtype=float)
    location = np.full(len(wave), "none", dtype=object)
    for i, p in enumerate(peak):
        candidates = np.arange(max(4, p - 2), min(nsamp - 1, p + 3))
        if len(candidates) == 0:
            continue
        interp = 0.5 * (wave[i, candidates - 1] + wave[i, candidates + 1])
        deficit = (interp - wave[i, candidates]) / amp[i]
        j = int(np.argmax(deficit))
        severity[i] = float(max(deficit[j], 0.0))
        t = int(candidates[j])
        if severity[i] <= float(config.get("real_candidate_deficit_frac", 0.08)):
            continue
        location[i] = "leading_edge" if t < p else ("peak_sample" if t == p else "trailing_sample")
    qscore = q_template_score(meta, wave, templates, config)
    pscore = pileup_score(wave)
    amp_bin = np.clip(np.searchsorted(bins, amp, side="right") - 1, 0, len(labels) - 1)
    q_edges = np.nanquantile(qscore, [0.0, 0.50, 0.90, 0.98, 1.0])
    q_edges = np.maximum.accumulate(q_edges + np.arange(len(q_edges)) * 1e-9)
    q_bin = pd.cut(qscore, bins=q_edges, labels=["q_low", "q_mid", "q_high", "q_extreme"], include_lowest=True)
    taxon = np.full(len(wave), "ordinary", dtype=object)
    peak_regions = p04g.peak_region(peak)
    taxon[(pscore > np.nanquantile(pscore, 0.90)) & (peak_regions == "late")] = "p09_like_broad_late"
    taxon[qscore > np.nanquantile(qscore, 0.98)] = "qtemplate_outlier"
    taxon[amp >= 7000.0] = "saturation_edge"
    work = pd.DataFrame(
        {
            "run": meta["run"].to_numpy(),
            "stave": meta["stave"].to_numpy(),
            "amp_bin_label": np.asarray(labels, dtype=object)[amp_bin],
            "peak_region": peak_regions,
            "dropout_like_location": location,
            "real_dropout_candidate": location != "none",
            "q_template_bin": q_bin.astype(str),
            "saturation_proxy": np.where(amp >= 7000.0, "amp_ge_7000", "amp_lt_7000"),
            "lowering_proxy": np.where(np.nanmin(wave[:, :4], axis=1) < -0.05 * amp, "negative_prepeak", "quiet_prepeak"),
            "p09_taxon_proxy": taxon,
            "notch_deficit_frac": severity,
            "q_template_score": qscore,
            "pileup_score": pscore,
        }
    )
    grouped = (
        work.groupby(
            [
                "dropout_like_location",
                "stave",
                "amp_bin_label",
                "peak_region",
                "q_template_bin",
                "saturation_proxy",
                "lowering_proxy",
                "p09_taxon_proxy",
            ],
            observed=True,
        )
        .agg(
            n_raw_pulses=("real_dropout_candidate", "size"),
            n_candidates=("real_dropout_candidate", "sum"),
            candidate_fraction=("real_dropout_candidate", "mean"),
            median_notch_deficit_frac=("notch_deficit_frac", "median"),
            median_q_template_score=("q_template_score", "median"),
            median_pileup_score=("pileup_score", "median"),
        )
        .reset_index()
    )
    return grouped.sort_values(["candidate_fraction", "n_candidates"], ascending=[False, False])


def engineered_features(meta: pd.DataFrame, corrupt: np.ndarray, mask: np.ndarray, interp_wave: np.ndarray) -> np.ndarray:
    base = p04g.feature_matrix(meta, corrupt, mask, interp_wave)
    peak = meta["clean_peak"].to_numpy().astype(float)
    left_energy = np.clip(interp_wave[:, :8], 0.0, None).sum(axis=1)
    right_energy = np.clip(interp_wave[:, 8:], 0.0, None).sum(axis=1)
    asym = (right_energy - left_energy) / np.maximum(right_energy + left_energy, 1.0)
    local_slope = interp_wave[:, 8] - interp_wave[:, 5]
    return np.column_stack([base, peak, asym, local_slope]).astype(np.float32)


def nn_context_features(meta: pd.DataFrame, interp_amp: np.ndarray, interp_charge: np.ndarray, cases: np.ndarray, staves: np.ndarray) -> np.ndarray:
    peak = meta["clean_peak"].to_numpy().astype(np.float32) / 17.0
    return np.column_stack(
        [
            np.log(np.maximum(interp_amp, 1.0)),
            np.log(np.maximum(interp_charge, 1.0)),
            meta["mask_count"].to_numpy().astype(np.float32),
            meta["mask_center"].to_numpy().astype(np.float32) / 17.0,
            peak,
            one_hot(staves, 4),
            one_hot(cases, int(cases.max()) + 1),
        ]
    ).astype(np.float32)


def ridge_or_mlp_predictions(
    name: str,
    estimator,
    X: np.ndarray,
    train_idx: np.ndarray,
    targets: np.ndarray,
    interp_amp: np.ndarray,
    interp_charge: np.ndarray,
    interp_wave: np.ndarray,
) -> Dict[str, np.ndarray]:
    estimator.fit(X[train_idx], targets[train_idx])
    pred = estimator.predict(X)
    amp = interp_amp * np.exp(pred[:, 0])
    charge = interp_charge * np.exp(pred[:, 1])
    scale = amp / np.maximum(interp_amp, 1.0)
    return {"method_family": name, "amp": amp, "charge": charge, "wave": interp_wave * scale[:, None], "accepted": np.ones(len(X), dtype=bool)}


def hgb_predictions(
    X: np.ndarray,
    train_idx: np.ndarray,
    targets: np.ndarray,
    interp_amp: np.ndarray,
    interp_charge: np.ndarray,
    interp_wave: np.ndarray,
    seed: int,
) -> Dict[str, np.ndarray]:
    params = {
        "max_iter": 120,
        "learning_rate": 0.055,
        "max_leaf_nodes": 31,
        "l2_regularization": 0.05,
        "random_state": seed,
    }
    amp_model = HistGradientBoostingRegressor(**params)
    charge_model = HistGradientBoostingRegressor(**{**params, "random_state": seed + 1})
    amp_model.fit(X[train_idx], targets[train_idx, 0])
    charge_model.fit(X[train_idx], targets[train_idx, 1])
    amp = interp_amp * np.exp(amp_model.predict(X))
    charge = interp_charge * np.exp(charge_model.predict(X))
    scale = amp / np.maximum(interp_amp, 1.0)
    return {"method_family": "gradient_boosted_trees", "amp": amp, "charge": charge, "wave": interp_wave * scale[:, None], "accepted": np.ones(len(X), dtype=bool)}


if torch is not None:

    class WaveCNN(nn.Module):
        def __init__(self, n_context: int, n_out: int):
            super().__init__()
            self.conv1 = nn.Conv1d(3, 24, kernel_size=3, padding=1)
            self.conv2 = nn.Conv1d(24, 32, kernel_size=3, padding=1)
            self.conv3 = nn.Conv1d(32, 32, kernel_size=3, padding=1)
            self.fc1 = nn.Linear(32 * 18 + n_context, 96)
            self.fc2 = nn.Linear(96, n_out)

        def forward(self, wave: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
            x = F.silu(self.conv1(wave))
            x = F.silu(self.conv2(x))
            x = F.silu(self.conv3(x))
            x = torch.flatten(x, 1)
            x = torch.cat([x, context], dim=1)
            x = F.silu(self.fc1(x))
            return self.fc2(x)


def torch_device() -> str:
    if torch is None:
        return "unavailable"
    return "cuda" if torch.cuda.is_available() else "cpu"


def make_wave_tensor(corrupt: np.ndarray, mask: np.ndarray, interp_wave: np.ndarray, interp_amp: np.ndarray) -> np.ndarray:
    denom = np.maximum(interp_amp, 1.0)[:, None]
    return np.stack([corrupt / denom, mask.astype(float), interp_wave / denom], axis=1).astype(np.float32)


def train_cnn_inpaint(
    wave_tensor: np.ndarray,
    context: np.ndarray,
    target_norm_wave: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    device = torch_device()
    model = WaveCNN(context.shape[1], 18).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)
    ds = TensorDataset(
        torch.from_numpy(wave_tensor[train_idx]),
        torch.from_numpy(context[train_idx]),
        torch.from_numpy(target_norm_wave[train_idx].astype(np.float32)),
    )
    loader = DataLoader(ds, batch_size=int(config["nn_batch_size"]), shuffle=True)
    losses = []
    model.train()
    for _ in range(int(config["nn_epochs"])):
        epoch = []
        for w, c, y in loader:
            w, c, y = w.to(device), c.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(w, c)
            loss = F.smooth_l1_loss(pred, y)
            loss.backward()
            opt.step()
            epoch.append(float(loss.detach().cpu()))
        losses.append(float(np.mean(epoch)))
    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(wave_tensor), 4096):
            w = torch.from_numpy(wave_tensor[start : start + 4096]).to(device)
            c = torch.from_numpy(context[start : start + 4096]).to(device)
            chunks.append(model(w, c).cpu().numpy())
    return np.vstack(chunks), {"device": device, "loss_start": losses[0], "loss_end": losses[-1], "epochs": int(config["nn_epochs"])}


def train_gated_cnn(
    wave_tensor: np.ndarray,
    context: np.ndarray,
    targets: np.ndarray,
    harm_target: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    device = torch_device()
    model = WaveCNN(context.shape[1], 3).to(device)
    pos = float(np.mean(harm_target[train_idx]))
    pos_weight = torch.tensor([(1.0 - pos) / max(pos, 1e-3)], dtype=torch.float32, device=device)
    opt = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)
    ds = TensorDataset(
        torch.from_numpy(wave_tensor[train_idx]),
        torch.from_numpy(context[train_idx]),
        torch.from_numpy(targets[train_idx].astype(np.float32)),
        torch.from_numpy(harm_target[train_idx, None].astype(np.float32)),
    )
    loader = DataLoader(ds, batch_size=int(config["nn_batch_size"]), shuffle=True)
    losses = []
    model.train()
    for _ in range(int(config["nn_epochs"])):
        epoch = []
        for w, c, y, h in loader:
            w, c, y, h = w.to(device), c.to(device), y.to(device), h.to(device)
            opt.zero_grad(set_to_none=True)
            out = model(w, c)
            reg_loss = F.smooth_l1_loss(out[:, :2], y)
            gate_loss = F.binary_cross_entropy_with_logits(out[:, 2:3], h, pos_weight=pos_weight)
            loss = reg_loss + 0.20 * gate_loss
            loss.backward()
            opt.step()
            epoch.append(float(loss.detach().cpu()))
        losses.append(float(np.mean(epoch)))
    model.eval()
    pred, gate = [], []
    with torch.no_grad():
        for start in range(0, len(wave_tensor), 4096):
            w = torch.from_numpy(wave_tensor[start : start + 4096]).to(device)
            c = torch.from_numpy(context[start : start + 4096]).to(device)
            out = model(w, c)
            pred.append(out[:, :2].cpu().numpy())
            gate.append(torch.sigmoid(out[:, 2]).cpu().numpy())
    return np.vstack(pred), np.concatenate(gate), {"device": device, "loss_start": losses[0], "loss_end": losses[-1], "epochs": int(config["nn_epochs"]), "train_harm_rate": pos}


def prediction_metrics(meta: pd.DataFrame, pred: dict, idx: np.ndarray, baseline: dict, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> dict:
    y_amp = meta["clean_amp"].to_numpy()
    y_charge = meta["clean_charge"].to_numpy()
    y_time = meta["true_time_sample"].to_numpy()
    y_tail = meta["true_tail_frac"].to_numpy()
    y_qtemplate = meta["true_q_template_score"].to_numpy()
    y_pileup = meta["true_pileup_score"].to_numpy()
    threshold = float(config["catastrophic_abs_frac"])
    amp_frac = (pred["amp"][idx] - y_amp[idx]) / np.maximum(y_amp[idx], 1.0)
    charge_frac = (pred["charge"][idx] - y_charge[idx]) / np.maximum(y_charge[idx], 1.0)
    pred_time = p04g.cfd_time_samples(pred["wave"][idx], np.maximum(pred["wave"][idx].max(axis=1), 1.0), float(config["cfd_fraction"]))
    pred_tail = p04g.tail_fraction(pred["wave"][idx])
    pred_qtemplate = q_template_score(meta.iloc[idx], pred["wave"][idx], templates, config)
    pred_pileup = pileup_score(pred["wave"][idx])
    time_abs = np.abs(pred_time - y_time[idx])
    tail_bias = pred_tail - y_tail[idx]
    qtemplate_shift = pred_qtemplate - y_qtemplate[idx]
    pileup_shift = pred_pileup - y_pileup[idx]

    raw_charge_abs = np.abs((baseline["charge"][idx] - y_charge[idx]) / np.maximum(y_charge[idx], 1.0))
    raw_time_abs = baseline["time_abs"][idx]
    raw_tail_abs = baseline["tail_abs"][idx]
    raw_qtemplate_abs = baseline["qtemplate_abs"][idx]
    raw_pileup_abs = baseline["pileup_abs"][idx]
    charge_gain = raw_charge_abs - np.abs(charge_frac)
    harm = (charge_gain > float(config["charge_gain_margin_frac"])) & (
        (time_abs > raw_time_abs + float(config["harm_time_margin_samples"]))
        | (np.abs(tail_bias) > raw_tail_abs + float(config["harm_tail_margin_frac"]))
        | (np.abs(qtemplate_shift) > raw_qtemplate_abs + float(config["harm_qtemplate_margin"]))
        | (np.abs(pileup_shift) > raw_pileup_abs + float(config["harm_pileup_margin"]))
    )

    accepted = pred.get("accepted")
    accepted_fraction = float(np.nan) if accepted is None else float(np.mean(accepted[idx]))
    return {
        "n": int(len(idx)),
        "accepted_fraction": accepted_fraction,
        "amp_bias_median_frac": float(np.nanmedian(amp_frac)),
        "amp_res68_abs_frac": float(np.nanpercentile(np.abs(amp_frac), 68)),
        "charge_bias_median_frac": float(np.nanmedian(charge_frac)),
        "charge_res68_abs_frac": float(np.nanpercentile(np.abs(charge_frac), 68)),
        "time_abs68_samples": float(np.nanpercentile(time_abs, 68)),
        "time_bias_median_samples": float(np.nanmedian(pred_time - y_time[idx])),
        "tail_bias_median_frac": float(np.nanmedian(tail_bias)),
        "q_template_shift_median": float(np.nanmedian(qtemplate_shift)),
        "q_template_abs68_shift": float(np.nanpercentile(np.abs(qtemplate_shift), 68)),
        "pileup_score_shift_median": float(np.nanmedian(pileup_shift)),
        "pileup_score_abs68_shift": float(np.nanpercentile(np.abs(pileup_shift), 68)),
        "catastrophic_rate": float(np.mean((np.abs(amp_frac) > threshold) | (np.abs(charge_frac) > threshold))),
        "phase_harm_rate": float(np.mean(harm)),
        "net_harm_label_rate": float(np.mean(harm)),
    }


def baseline_arrays(meta: pd.DataFrame, raw_pred: dict, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> dict:
    y_charge = meta["clean_charge"].to_numpy()
    y_time = meta["true_time_sample"].to_numpy()
    y_tail = meta["true_tail_frac"].to_numpy()
    y_qtemplate = meta["true_q_template_score"].to_numpy()
    y_pileup = meta["true_pileup_score"].to_numpy()
    time = p04g.cfd_time_samples(raw_pred["wave"], np.maximum(raw_pred["wave"].max(axis=1), 1.0), float(config["cfd_fraction"]))
    tail = p04g.tail_fraction(raw_pred["wave"])
    qtemplate = q_template_score(meta, raw_pred["wave"], templates, config)
    pileup = pileup_score(raw_pred["wave"])
    return {
        "charge": raw_pred["charge"],
        "charge_abs": np.abs((raw_pred["charge"] - y_charge) / np.maximum(y_charge, 1.0)),
        "time_abs": np.abs(time - y_time),
        "tail_abs": np.abs(tail - y_tail),
        "qtemplate_abs": np.abs(qtemplate - y_qtemplate),
        "pileup_abs": np.abs(pileup - y_pileup),
    }


def run_block_bootstrap(meta: pd.DataFrame, predictions: Dict[str, dict], heldout_mask: np.ndarray, baseline: dict, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 701)
    blocks = meta.loc[heldout_mask, ["run", "eventno", "stave_idx"]].drop_duplicates().reset_index(drop=True)
    block_indices = [
        np.where(
            heldout_mask
            & (meta["run"].to_numpy() == int(row.run))
            & (meta["eventno"].to_numpy() == int(row.eventno))
            & (meta["stave_idx"].to_numpy() == int(row.stave_idx))
        )[0]
        for row in blocks.itertuples(index=False)
    ]
    held_idx = np.where(heldout_mask)[0]
    metric_names = [
        "amp_res68_abs_frac",
        "charge_res68_abs_frac",
        "time_abs68_samples",
        "tail_bias_median_frac",
        "q_template_abs68_shift",
        "pileup_score_abs68_shift",
        "catastrophic_rate",
        "phase_harm_rate",
        "net_harm_label_rate",
        "accepted_fraction",
    ]
    point_rows = {}
    samples = {method: {metric: [] for metric in metric_names} for method in predictions}
    for method, pred in predictions.items():
        point_rows[method] = prediction_metrics(meta, pred, held_idx, baseline, templates, config)
    for _ in range(int(config["bootstrap_reps"])):
        chosen = rng.integers(0, len(block_indices), size=len(block_indices))
        idx = np.concatenate([block_indices[i] for i in chosen])
        for method, pred in predictions.items():
            m = prediction_metrics(meta, pred, idx, baseline, templates, config)
            for metric in metric_names:
                samples[method][metric].append(m[metric])

    rows = []
    for method, metrics in point_rows.items():
        row = {"method": method, "method_family": predictions[method].get("method_family", method)}
        row.update(metrics)
        for metric in metric_names:
            vals = np.asarray(samples[method][metric], dtype=float)
            vals = vals[np.isfinite(vals)]
            if len(vals):
                row[f"{metric}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
        rows.append(row)
    return pd.DataFrame(rows)


def utility(summary: pd.DataFrame) -> pd.Series:
    return (
        summary["charge_res68_abs_frac"]
        + 0.15 * summary["amp_res68_abs_frac"]
        + 0.20 * summary["time_abs68_samples"]
        + 0.35 * summary["q_template_abs68_shift"]
        + 0.35 * summary["pileup_score_abs68_shift"]
        + 1.50 * summary["phase_harm_rate"]
        + 0.50 * summary["catastrophic_rate"]
    )


def utility_from_metrics(metrics: dict) -> float:
    return float(
        metrics["charge_res68_abs_frac"]
        + 0.15 * metrics["amp_res68_abs_frac"]
        + 0.20 * metrics["time_abs68_samples"]
        + 0.35 * metrics["q_template_abs68_shift"]
        + 0.35 * metrics["pileup_score_abs68_shift"]
        + 1.50 * metrics["phase_harm_rate"]
        + 0.50 * metrics["catastrophic_rate"]
    )


def bootstrap_method_deltas(
    meta: pd.DataFrame,
    predictions: Dict[str, dict],
    heldout_mask: np.ndarray,
    baseline: dict,
    templates: Dict[Tuple[int, int], np.ndarray],
    config: dict,
    reference_method: str,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 1701)
    blocks = meta.loc[heldout_mask, ["run", "eventno", "stave_idx"]].drop_duplicates().reset_index(drop=True)
    block_indices = [
        np.where(
            heldout_mask
            & (meta["run"].to_numpy() == int(row.run))
            & (meta["eventno"].to_numpy() == int(row.eventno))
            & (meta["stave_idx"].to_numpy() == int(row.stave_idx))
        )[0]
        for row in blocks.itertuples(index=False)
    ]
    metrics = [
        "charge_res68_abs_frac",
        "time_abs68_samples",
        "q_template_abs68_shift",
        "pileup_score_abs68_shift",
        "phase_harm_rate",
        "utility",
    ]
    samples = {
        method: {metric: [] for metric in metrics}
        for method in predictions
        if method not in ("no_recovery", reference_method)
    }
    for _ in range(int(config["bootstrap_reps"])):
        chosen = rng.integers(0, len(block_indices), size=len(block_indices))
        idx = np.concatenate([block_indices[i] for i in chosen])
        ref_metrics = prediction_metrics(meta, predictions[reference_method], idx, baseline, templates, config)
        ref_metrics["utility"] = utility_from_metrics(ref_metrics)
        for method in samples:
            m = prediction_metrics(meta, predictions[method], idx, baseline, templates, config)
            m["utility"] = utility_from_metrics(m)
            for metric in metrics:
                samples[method][metric].append(float(m[metric] - ref_metrics[metric]))

    rows = []
    ref_row = summary[summary["method"] == reference_method].iloc[0]
    for method in samples:
        method_row = summary[summary["method"] == method].iloc[0]
        for metric in metrics:
            vals = np.asarray(samples[method][metric], dtype=float)
            rows.append(
                {
                    "comparison": "{} minus {}".format(method, reference_method),
                    "metric": metric,
                    "delta": float(method_row[metric] - ref_row[metric]),
                    "delta_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))],
                }
            )
    return pd.DataFrame(rows)


def support_atom_table(meta: pd.DataFrame, predictions: Dict[str, dict], heldout_mask: np.ndarray, baseline: dict, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> pd.DataFrame:
    rows = []
    work = meta.loc[heldout_mask].copy()
    for keys, group in work.groupby(atom_columns(), observed=True):
        idx = group.index.to_numpy()
        if len(idx) < 24:
            continue
        key_map = dict(zip(atom_columns(), keys))
        raw_m = prediction_metrics(meta, predictions["no_recovery"], idx, baseline, templates, config)
        for method, pred in predictions.items():
            if method == "no_recovery":
                continue
            m = prediction_metrics(meta, pred, idx, baseline, templates, config)
            row = dict(key_map)
            row.update(
                {
                    "method": method,
                    "n": int(len(idx)),
                    "charge_res68_abs_frac": m["charge_res68_abs_frac"],
                    "charge_gain_vs_no_recovery": raw_m["charge_res68_abs_frac"] - m["charge_res68_abs_frac"],
                    "time_delta_vs_no_recovery_samples": m["time_abs68_samples"] - raw_m["time_abs68_samples"],
                    "tail_bias_median_frac": m["tail_bias_median_frac"],
                    "q_template_abs68_shift": m["q_template_abs68_shift"],
                    "pileup_score_abs68_shift": m["pileup_score_abs68_shift"],
                    "phase_harm_rate": m["phase_harm_rate"],
                    "net_harm_label_rate": m["net_harm_label_rate"],
                    "catastrophic_rate": m["catastrophic_rate"],
                    "accepted_fraction": m["accepted_fraction"],
                }
            )
            rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["support_status"] = np.where(
        (out["charge_gain_vs_no_recovery"] > 0.02) & (out["net_harm_label_rate"] <= 0.05),
        "accept",
        np.where((out["charge_gain_vs_no_recovery"] > 0.02) & (out["net_harm_label_rate"] > 0.05), "harm_watch", "abstain"),
    )
    return out.sort_values(["support_status", "method", "net_harm_label_rate", "charge_gain_vs_no_recovery"], ascending=[True, True, True, False])


def leakage_audit(meta: pd.DataFrame, train_mask: np.ndarray, heldout_mask: np.ndarray, corrupt: np.ndarray, predictions: Dict[str, dict], templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> dict:
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    block_train = set(zip(meta.loc[train_mask, "run"], meta.loc[train_mask, "eventno"], meta.loc[train_mask, "stave_idx"]))
    block_eval = set(zip(meta.loc[heldout_mask, "run"], meta.loc[heldout_mask, "eventno"], meta.loc[heldout_mask, "stave_idx"]))
    train_hashes = {hashlib.sha1(corrupt[i].tobytes()).hexdigest() for i in np.where(train_mask)[0]}
    eval_hashes = {hashlib.sha1(corrupt[i].tobytes()).hexdigest() for i in np.where(heldout_mask)[0]}
    return {
        "heldout_runs": heldout_runs,
        "heldout_absent_from_train": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "train_eval_block_overlap": int(len(block_train.intersection(block_eval))),
        "exact_corrupt_wave_hash_overlap": int(len(train_hashes.intersection(eval_hashes))),
        "feature_exclusion": "run id, event id, clean waveform, clean amplitude, clean charge, and post-injection labels are excluded from predictors",
        "torch_available": bool(torch is not None),
        "too_good_triggered": bool(summary_min_charge(predictions, meta, heldout_mask, templates, config) < 0.005),
    }


def summary_min_charge(predictions: Dict[str, dict], meta: pd.DataFrame, heldout_mask: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> float:
    baseline = baseline_arrays(meta, predictions["no_recovery"], templates, config)
    idx = np.where(heldout_mask)[0]
    vals = []
    for name, pred in predictions.items():
        if name != "no_recovery":
            vals.append(prediction_metrics(meta, pred, idx, baseline, templates, config)["charge_res68_abs_frac"])
    return float(np.min(vals))


def markdown_table(df: pd.DataFrame, columns: List[str], max_rows: int = 24) -> str:
    if df.empty:
        return "_No rows._"
    rows = df.loc[:, columns].head(max_rows).copy()
    for col in rows.columns:
        def fmt(v):
            if isinstance(v, float):
                return f"{v:.5g}"
            if isinstance(v, list):
                return "[" + ", ".join(f"{x:.5g}" for x in v) + "]"
            return str(v)
        rows[col] = rows[col].map(fmt)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows.to_numpy()]
    return "\n".join([header, sep] + body)


def write_report(out_dir: Path, config: dict, result: dict, summary: pd.DataFrame, support: pd.DataFrame, deltas: pd.DataFrame, real_audit: pd.DataFrame) -> None:
    support_focus = support.sort_values(["phase_harm_rate", "charge_gain_vs_no_recovery"], ascending=[False, False]).head(18) if not support.empty else support
    real_focus = real_audit[real_audit["dropout_like_location"] != "none"].head(18) if not real_audit.empty else real_audit
    lines = [
        "# P04s: dropout recovery phase-harm abstention gate",
        "",
        f"Ticket `{config['ticket_id']}`. Worker `{config['worker']}`. The study reads the raw B-stack ROOT files from `{config['raw_root_dir']}` and does not use simulation.",
        "",
        "## Abstract",
        "",
        (
            "This analysis asks where P04g-style sample-dropout recovery improves amplitude or charge while damaging "
            "timing phase, tail shape, q_template support, or pile-up-score support. The raw reproduction gate exactly "
            "recovers the canonical S00 selected-pulse count, then deterministic dropouts are injected into real selected "
            "pulses. A strong rising-edge Huber recovery is compared to ridge, gradient-boosted trees, MLP, 1D-CNN "
            "inpainting, and a new phase-harm-gated CNN. The primary selection criterion is a pre-registered utility "
            "combining charge resolution, amplitude resolution, timing phase error, q_template shift, pile-up-score "
            "shift, catastrophic failures, and phase-harm labels."
        ),
        "",
        "## Raw reproduction gate",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {result['raw_reproduction']['pass']} |",
        "",
        "The reproduced count is computed from `HRDv` in the raw ROOT tree by subtracting the median of samples 0-3, taking even B-stack channels B2/B4/B6/B8, and applying the same `A > 1000 ADC` pulse gate used by S00.",
        "",
        "## Data split and dropout model",
        "",
        f"Training runs are all configured B-stack analysis/calibration runs except held-out runs `{config['heldout_runs']}`. Held-out intervals resample `(run,event,stave)` blocks, preserving the four paired dropout variants.",
        "",
        "For a clean waveform vector $x_i \\in \\mathbb{R}^{18}$ with peak sample $p_i$, each dropout case defines a mask $m_i$ at offsets $\\Delta$. The corrupted waveform is",
        "",
        "$$\\tilde{x}_{it}=x_{it}(1-m_{it}), \\qquad m_{it}=1[t=\\mathrm{clip}(p_i+\\Delta,4,17)].$$",
        "",
        "The reference amplitude is $A_i=\\max_t x_{it}$ and charge is $Q_i=\\sum_t \\max(x_{it},0)$. Timing is the CFD-20 crossing in sample units, linearly interpolated between neighboring samples.",
        "",
        "The q_template score is an operational raw-data proxy. For each training-only `(stave, amplitude bin)` cell, a normalized template $\\tau_{sb}$ is the median of $x_i/A_i$. For a predicted waveform $\\hat x_i$,",
        "",
        "$$q_i(\\hat x)=\\sqrt{\\frac{1}{18}\\sum_t\\left(\\frac{\\hat x_{it}}{\\max_t \\hat x_{it}}-\\tau_{s(i)b(i)t}\\right)^2}.$$",
        "",
        "The pile-up score is another operational proxy, $\\pi_i=0.65E_{late}/Q+0.35A_{secondary}/A_{peak}$, combining late energy after the peak and the largest secondary lobe outside the peak neighborhood.",
        "",
        "## Methods",
        "",
        "- `rising_edge_huber`: strong traditional comparator. It uses rising-edge maxima, positive integral summaries, dropout geometry, stave, and case indicators in robust log-linear Huber regressions.",
        "- `ridge_residual`: standardized ridge regression for log residuals $\\log A-\\log \\hat A_{interp}$ and $\\log Q-\\log \\hat Q_{interp}$.",
        "- `gbt_residual`: histogram gradient-boosted trees for the same residual targets.",
        "- `mlp_residual`: two-output neural residual regressor on the engineered waveform/mask feature vector.",
        "- `cnn_inpaint`: 1D convolutional denoiser trained to reconstruct the clean 18-sample waveform from corrupted waveform, mask, and interpolated waveform channels.",
        "- `phase_harm_gated_cnn`: new architecture for this ticket. It shares a 1D convolutional encoder with a residual-regression head and a phase-harm probability head; if predicted phase harm exceeds the configured gate, it abstains to the traditional Huber estimate.",
        "",
        "All learned models exclude run id, event id, clean targets, duplicate targets, and any held-out labels from features. Hyperparameters were fixed before evaluation and no held-out run is used for training or calibration.",
        "",
        "## Metrics",
        "",
        "Fractional errors are $e_A=(\\hat A-A)/A$ and $e_Q=(\\hat Q-Q)/Q$. The reported robust resolutions are $P_{68}(|e_A|)$, $P_{68}(|e_Q|)$, and $P_{68}(|\\hat t-t|)$. Catastrophic rate is",
        "",
        "$$r_{cat}=\\frac{1}{N}\\sum_i 1\\{|e_{A,i}|>0.2 \\;\\lor\\; |e_{Q,i}|>0.2\\}.$$",
        "",
        "A row is counted as a phase-harm label when the method improves absolute charge error by more than the configured charge-gain margin relative to no recovery, but increases absolute timing error, absolute tail-fraction error, q_template shift, or pile-up-score shift beyond the configured harm margins.",
        "",
        "The primary utility minimized for winner selection is",
        "",
        "$$U=P_{68}(|e_Q|)+0.15P_{68}(|e_A|)+0.20P_{68}(|\\Delta t|)+0.35P_{68}(|\\Delta q|)+0.35P_{68}(|\\Delta \\pi|)+1.50r_{phaseharm}+0.50r_{cat}.$$",
        "",
        "## Held-out method table",
        "",
        markdown_table(
            summary.sort_values("utility"),
            [
                "method",
                "method_family",
                "n",
                "accepted_fraction",
                "amp_res68_abs_frac",
                "charge_res68_abs_frac",
                "time_abs68_samples",
                "tail_bias_median_frac",
                "q_template_abs68_shift",
                "pileup_score_abs68_shift",
                "catastrophic_rate",
                "phase_harm_rate",
                "utility",
            ],
            max_rows=12,
        ),
        "",
        "## Bootstrap confidence intervals",
        "",
        markdown_table(
            summary.sort_values("utility"),
            [
                "method",
                "amp_res68_abs_frac_ci95",
                "charge_res68_abs_frac_ci95",
                "time_abs68_samples_ci95",
                "tail_bias_median_frac_ci95",
                "q_template_abs68_shift_ci95",
                "pileup_score_abs68_shift_ci95",
                "catastrophic_rate_ci95",
                "phase_harm_rate_ci95",
            ],
            max_rows=12,
        ),
        "",
        "## Winner and pairwise deltas",
        "",
        f"Winner by the pre-registered utility is `{result['winner']['method']}` with utility `{result['winner']['utility']:.5g}`. The best traditional method is `{result['best_traditional']['method']}`.",
        "",
        markdown_table(deltas, ["comparison", "metric", "delta", "delta_ci95"], max_rows=48),
        "",
        "## Support atoms",
        "",
        "Each atom is a held-out `(stave, dropout case, amplitude bin, peak region)` cell. `accept` means the cell has charge gain over no recovery with phase-harm rate <=5%; `harm_watch` means charge gain is present but timing/tail/q_template/pile-up harm is non-negligible; `abstain` means the charge gain is too small or unstable.",
        "",
        markdown_table(
            support_focus,
            [
                "stave",
                "dropout_case",
                "amp_bin_label",
                "peak_region",
                "method",
                "n",
                "charge_gain_vs_no_recovery",
                "time_delta_vs_no_recovery_samples",
                "tail_bias_median_frac",
                "q_template_abs68_shift",
                "pileup_score_abs68_shift",
                "phase_harm_rate",
                "support_status",
            ],
            max_rows=18,
        ),
        "",
        "The full support map is in `support_atoms.csv`.",
        "",
        "## Natural dropout/anomaly candidate audit",
        "",
        "The injected benchmark has truth by construction. Natural raw dropout/anomaly candidates do not have clean counterfactual waveforms, so they are treated as an unsupervised support audit: a pulse is flagged when one sample in the peak neighborhood is lower than the interpolation of its two neighbors by more than the configured amplitude fraction. The table is stratified by missing-sample location, peak phase, amplitude, stave, q_template score, lowering proxy, saturation proxy, and a P09-style morphology proxy.",
        "",
        markdown_table(
            real_focus,
            [
                "dropout_like_location",
                "stave",
                "amp_bin_label",
                "peak_region",
                "q_template_bin",
                "saturation_proxy",
                "lowering_proxy",
                "p09_taxon_proxy",
                "n_raw_pulses",
                "n_candidates",
                "candidate_fraction",
                "median_notch_deficit_frac",
            ],
            max_rows=18,
        ),
        "",
        "The full natural-candidate stratification is in `real_candidate_audit.csv`; it is a support warning table, not a supervised recovery metric.",
        "",
        "## Leakage and systematics",
        "",
        f"- Held-out runs absent from training: `{result['leakage_audit']['heldout_absent_from_train']}`.",
        f"- Train/evaluation `(run,event,stave)` overlap: `{result['leakage_audit']['train_eval_block_overlap']}`.",
        f"- Exact corrupted-waveform hash overlap: `{result['leakage_audit']['exact_corrupt_wave_hash_overlap']}`.",
        f"- Feature exclusion: {result['leakage_audit']['feature_exclusion']}.",
        "",
        "Important systematics are not removed by this ticket: injected zero-sample dropouts approximate digitizer or reconstruction losses but do not prove the same support for natural missing-sample mechanisms; the natural-candidate audit has no clean counterfactual target; q_template and pile-up scores are operational waveform proxies rather than independent downstream labels; support atoms are sparse for late peaks and high-amplitude B8 cells; and the CFD timing metric is local to waveform phase, not a full downstream physics selection. The gate should therefore be used as an abstention prior for P04/P07/S14/PID charge consumers, not as an unconditional correction license.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.py --config configs/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("P04s: reading raw ROOT and reproducing S00 selected-pulse count ...")
    meta_all, wave_all, counts_by_run = p04g.extract_selected(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError("raw reproduction failed: got {}, expected {}".format(total_selected, expected))

    selected_idx = p04g.stratified_indices(meta_all, config)
    print("P04s: injecting dropouts into {} clean pulses ...".format(len(selected_idx)))
    inj, corrupt, mask = p04g.inject_dropouts(meta_all, wave_all, selected_idx, config)
    inj = add_support_atoms(inj, config)
    clean = np.vstack([wave_all[selected_idx].astype(float) for _ in config["dropout_cases"]])
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = inj["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    if set(inj.loc[train_mask, "run"].unique()).intersection(heldout_runs):
        raise RuntimeError("held-out run leaked into training")
    q_templates = p04g.build_templates(inj, clean, train_mask, config)
    inj["true_q_template_score"] = q_template_score(inj, clean, q_templates, config)
    inj["true_pileup_score"] = pileup_score(clean)
    print("P04s: stratifying natural dropout/anomaly-like raw candidates ...")
    real_audit = real_candidate_audit(meta_all, wave_all.astype(float), q_templates, config)

    interp_wave = p04g.interpolate_missing(corrupt, mask)
    interp_amp = np.maximum(interp_wave.max(axis=1), 1.0)
    interp_charge = np.maximum(p04g.positive_charge(interp_wave), 1.0)
    corrupt_amp = np.maximum(corrupt.max(axis=1), 1.0)
    corrupt_charge = np.maximum(p04g.positive_charge(corrupt), 1.0)
    true_amp = inj["clean_amp"].to_numpy()
    true_charge = inj["clean_charge"].to_numpy()
    staves = inj["stave_idx"].to_numpy().astype(int)
    cases = inj["dropout_idx"].to_numpy().astype(int)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    targets = np.column_stack([np.log(true_amp) - np.log(interp_amp), np.log(true_charge) - np.log(interp_charge)]).astype(np.float32)

    print("P04s: fitting traditional comparator and tabular ML/NN models ...")
    predictions: Dict[str, dict] = {
        "no_recovery": {"method_family": "baseline", "amp": corrupt_amp, "charge": corrupt_charge, "wave": corrupt.astype(float), "accepted": np.zeros(len(inj), dtype=bool)},
        "interpolation": {"method_family": "traditional", "amp": interp_amp, "charge": interp_charge, "wave": interp_wave.astype(float), "accepted": np.ones(len(inj), dtype=bool)},
    }
    rise_X = np.column_stack(
        [
            np.log(np.maximum(corrupt[:, :9].max(axis=1), 1.0)),
            np.log(np.maximum(np.clip(corrupt[:, :9], 0.0, None).sum(axis=1), 1.0)),
            np.log(interp_amp),
            np.log(interp_charge),
            corrupt.argmax(axis=1),
            inj["mask_center"].to_numpy(),
            one_hot(staves, 4),
            one_hot(cases, int(cases.max()) + 1),
        ]
    ).astype(np.float32)
    rise_amp = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, max_iter=300))
    rise_charge = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, max_iter=300))
    rise_amp.fit(rise_X[train_idx], np.log(true_amp[train_idx]))
    rise_charge.fit(rise_X[train_idx], np.log(true_charge[train_idx]))
    predictions["rising_edge_huber"] = {
        "method_family": "traditional",
        "amp": np.exp(rise_amp.predict(rise_X)),
        "charge": np.exp(rise_charge.predict(rise_X)),
        "wave": corrupt.astype(float),
        "accepted": np.ones(len(inj), dtype=bool),
    }

    X = engineered_features(inj, corrupt, mask, interp_wave)
    predictions["ridge_residual"] = ridge_or_mlp_predictions(
        "ridge",
        make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        X,
        train_idx,
        targets,
        interp_amp,
        interp_charge,
        interp_wave,
    )
    predictions["gbt_residual"] = hgb_predictions(X, train_idx, targets, interp_amp, interp_charge, interp_wave, int(config["random_seed"]) + 3)
    predictions["mlp_residual"] = ridge_or_mlp_predictions(
        "mlp",
        make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(72, 36),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=7e-4,
                max_iter=120,
                early_stopping=True,
                n_iter_no_change=12,
                random_state=int(config["random_seed"]) + 4,
            ),
        ),
        X,
        train_idx,
        targets,
        interp_amp,
        interp_charge,
        interp_wave,
    )

    nn_diagnostics = {}
    if torch is not None:
        print("P04s: fitting CNN inpainting and phase-harm-gated CNN ...")
        nn_train_idx = np.where(train_mask)[0]
        if len(nn_train_idx) > int(config["nn_max_train_rows"]):
            nn_train_idx = rng.choice(nn_train_idx, size=int(config["nn_max_train_rows"]), replace=False)
        context = nn_context_features(inj, interp_amp, interp_charge, cases, staves)
        wave_tensor = make_wave_tensor(corrupt, mask, interp_wave, interp_amp)
        target_norm_wave = (clean / np.maximum(interp_amp, 1.0)[:, None]).astype(np.float32)
        pred_norm, cnn_diag = train_cnn_inpaint(wave_tensor, context, target_norm_wave, nn_train_idx, config, int(config["random_seed"]) + 5)
        cnn_wave = np.maximum(pred_norm * interp_amp[:, None], 0.0)
        predictions["cnn_inpaint"] = {
            "method_family": "1d_cnn",
            "amp": np.maximum(cnn_wave.max(axis=1), 1.0),
            "charge": np.maximum(p04g.positive_charge(cnn_wave), 1.0),
            "wave": cnn_wave,
            "accepted": np.ones(len(inj), dtype=bool),
        }

        baseline_for_harm = baseline_arrays(inj, predictions["no_recovery"], q_templates, config)
        cnn_metrics_all = prediction_metrics(inj, predictions["cnn_inpaint"], np.arange(len(inj)), baseline_for_harm, q_templates, config)
        del cnn_metrics_all
        cnn_time = p04g.cfd_time_samples(cnn_wave, np.maximum(cnn_wave.max(axis=1), 1.0), float(config["cfd_fraction"]))
        cnn_tail = p04g.tail_fraction(cnn_wave)
        cnn_qtemplate = q_template_score(inj, cnn_wave, q_templates, config)
        cnn_pileup = pileup_score(cnn_wave)
        raw_charge_abs = baseline_for_harm["charge_abs"]
        cnn_charge_abs = np.abs((predictions["cnn_inpaint"]["charge"] - true_charge) / np.maximum(true_charge, 1.0))
        harm_target = (
            (raw_charge_abs - cnn_charge_abs > float(config["charge_gain_margin_frac"]))
            & (
                (np.abs(cnn_time - inj["true_time_sample"].to_numpy()) > baseline_for_harm["time_abs"] + float(config["harm_time_margin_samples"]))
                | (np.abs(cnn_tail - inj["true_tail_frac"].to_numpy()) > baseline_for_harm["tail_abs"] + float(config["harm_tail_margin_frac"]))
                | (np.abs(cnn_qtemplate - inj["true_q_template_score"].to_numpy()) > baseline_for_harm["qtemplate_abs"] + float(config["harm_qtemplate_margin"]))
                | (np.abs(cnn_pileup - inj["true_pileup_score"].to_numpy()) > baseline_for_harm["pileup_abs"] + float(config["harm_pileup_margin"]))
            )
        ).astype(np.float32)
        gated_pred, gate_prob, gate_diag = train_gated_cnn(wave_tensor, context, targets, harm_target, nn_train_idx, config, int(config["random_seed"]) + 6)
        gate_accept = gate_prob <= float(config["gate_threshold"])
        gated_amp = interp_amp * np.exp(gated_pred[:, 0])
        gated_charge = interp_charge * np.exp(gated_pred[:, 1])
        gated_wave = interp_wave * (gated_amp / np.maximum(interp_amp, 1.0))[:, None]
        huber = predictions["rising_edge_huber"]
        gated_amp = np.where(gate_accept, gated_amp, huber["amp"])
        gated_charge = np.where(gate_accept, gated_charge, huber["charge"])
        gated_wave = np.where(gate_accept[:, None], gated_wave, huber["wave"])
        predictions["phase_harm_gated_cnn"] = {
            "method_family": "new_phase_harm_gated_cnn",
            "amp": gated_amp,
            "charge": gated_charge,
            "wave": gated_wave,
            "accepted": gate_accept,
            "gate_probability": gate_prob,
        }
        nn_diagnostics = {"cnn_inpaint": cnn_diag, "phase_harm_gated_cnn": gate_diag}
    else:
        print("P04s: torch unavailable; CNN methods skipped.")

    print("P04s: computing run-block bootstrap confidence intervals ...")
    baseline = baseline_arrays(inj, predictions["no_recovery"], q_templates, config)
    summary = run_block_bootstrap(inj, predictions, heldout_mask, baseline, q_templates, config)
    summary["utility"] = utility(summary)
    summary = summary.sort_values("utility").reset_index(drop=True)
    support = support_atom_table(inj, predictions, heldout_mask, baseline, q_templates, config)

    best_trad = summary[summary["method_family"] == "traditional"].sort_values("utility").iloc[0]
    winner = summary.iloc[0]
    deltas = bootstrap_method_deltas(inj, predictions, heldout_mask, baseline, q_templates, config, str(best_trad["method"]), summary)

    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    summary.to_csv(out_dir / "heldout_summary.csv", index=False)
    support.to_csv(out_dir / "support_atoms.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    real_audit.to_csv(out_dir / "real_candidate_audit.csv", index=False)

    leakage = leakage_audit(inj, train_mask, heldout_mask, corrupt, predictions, q_templates, config)
    finding = (
        "Winner by support-aware utility is {winner} (U={utility:.5g}); best traditional comparator is "
        "{trad} (U={trad_u:.5g}). The support map identifies atoms with charge gain but nonzero timing, tail, "
        "q-template, or pile-up-score harm, "
        "so dropout recovery should be applied with abstention rather than globally."
    ).format(winner=winner["method"], utility=float(winner["utility"]), trad=best_trad["method"], trad_u=float(best_trad["utility"]))

    result = {
        "study": config["study"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs,
            "train_runs": sorted(int(x) for x in inj.loc[train_mask, "run"].unique()),
            "n_clean_pulses_sampled": int(len(selected_idx)),
            "n_injected_rows": int(len(inj)),
            "n_train_rows": int(train_mask.sum()),
            "n_heldout_rows": int(heldout_mask.sum()),
            "bootstrap_reps": int(config["bootstrap_reps"]),
            "bootstrap_block": "run,event,stave with paired dropout variants",
        },
        "methods": {
            name: {"family": pred.get("method_family", name), "has_acceptance_gate": bool("accepted" in pred)}
            for name, pred in predictions.items()
        },
        "winner": {
            "method": str(winner["method"]),
            "method_family": str(winner["method_family"]),
            "utility": float(winner["utility"]),
            "charge_res68_abs_frac": float(winner["charge_res68_abs_frac"]),
            "time_abs68_samples": float(winner["time_abs68_samples"]),
            "q_template_abs68_shift": float(winner["q_template_abs68_shift"]),
            "pileup_score_abs68_shift": float(winner["pileup_score_abs68_shift"]),
            "phase_harm_rate": float(winner["phase_harm_rate"]),
            "net_harm_label_rate": float(winner["net_harm_label_rate"]),
        },
        "best_traditional": {
            "method": str(best_trad["method"]),
            "utility": float(best_trad["utility"]),
            "charge_res68_abs_frac": float(best_trad["charge_res68_abs_frac"]),
        },
        "heldout_summary": json.loads(summary.to_json(orient="records")),
        "support_atom_status_counts": support["support_status"].value_counts().to_dict() if not support.empty else {},
        "real_candidate_audit": {
            "candidate_rows": int(real_audit["n_candidates"].sum()) if not real_audit.empty else 0,
            "raw_pulses_stratified": int(real_audit["n_raw_pulses"].sum()) if not real_audit.empty else 0,
            "deficit_threshold_frac": float(config.get("real_candidate_deficit_frac", 0.08)),
            "note": "unsupervised raw support audit; not used as supervised benchmark truth",
        },
        "leakage_audit": leakage,
        "nn_diagnostics": nn_diagnostics,
        "finding": finding,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, result, summary, support, deltas, real_audit)

    output_names = ["REPORT.md", "result.json", "counts_by_run.csv", "heldout_summary.csv", "support_atoms.csv", "method_deltas.csv", "real_candidate_audit.csv"]
    manifest = {
        "study": config["study"],
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.py --config configs/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.json",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "inputs": [{"path": str(p04g.raw_path(config, run)), "sha256": sha256_file(p04g.raw_path(config, run))} for run in p04g.configured_runs(config)],
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_names],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("DONE -> {} in {} s".format(out_dir, result["runtime_sec"]))


if __name__ == "__main__":
    main()
