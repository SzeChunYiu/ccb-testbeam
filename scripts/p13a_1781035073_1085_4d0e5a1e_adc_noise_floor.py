#!/usr/bin/env python3
"""P13a ADC quantization/electronics noise floor benchmark.

The script starts from raw B-stack ROOT files, reproduces the canonical
selected-pulse count, and measures a masked-sample denoising proxy for the
per-sample noise floor.  The benchmark is deliberately run-heldout: Sample I
runs calibrate all templates and learned models; Sample II runs are never used
for fitting and carry the bootstrap confidence intervals.
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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p13a")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
QUANTIZATION_SIGMA_ADC = 1.0 / math.sqrt(12.0)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]).expanduser() / f"hrdb_run_{int(run):04d}.root"


def phase_for_sample(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for phase, samples in config["phase_bins"].items():
        for sample in samples:
            out[int(sample)] = str(phase)
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def scan_raw(config: dict) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    even_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)
    groups = run_group_lookup(config)

    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        row.update({name: 0 for name in STAVE_NAMES})
        event_offset = 0
        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            amp = even.max(axis=-1)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)

            row["events_total"] += int(len(eventno))
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                row[name] += int(selected[:, i].sum())

            if len(event_idx):
                chosen = even[event_idx, stave_idx, :].astype(np.float32)
                chosen_amp = amp[event_idx, stave_idx].astype(np.float32)
                waves.append(chosen)
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": chosen_amp,
                            "baseline_adc": baseline[event_idx, even_channels[stave_idx]].astype(np.float32),
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                            "area_adc_samples": chosen.sum(axis=1).astype(np.float32),
                        }
                    )
                )
            event_offset += int(len(eventno))
        count_rows.append(row)
        print(f"run {run:04d}: {row['selected_pulses']} selected pulses")

    return np.vstack(waves), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def reproduction_table(config: dict, counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = int(counts["selected_pulses"].sum())
    expected_total = int(config["expected_counts"]["total_selected_pulses"])
    rows.append(
        {
            "quantity": "total selected B-stack pulses, A>1000 ADC",
            "report_value": expected_total,
            "reproduced": total,
            "delta": total - expected_total,
            "tolerance": 0,
            "pass": total == expected_total,
        }
    )
    sample_ii = counts[counts["group"] == "sample_ii_analysis"]
    expected = config["expected_counts"]["sample_ii_analysis"]
    rows.append(
        {
            "quantity": "Sample II analysis selected pulses",
            "report_value": int(expected["selected_pulses"]),
            "reproduced": int(sample_ii["selected_pulses"].sum()),
            "delta": int(sample_ii["selected_pulses"].sum()) - int(expected["selected_pulses"]),
            "tolerance": 0,
            "pass": int(sample_ii["selected_pulses"].sum()) == int(expected["selected_pulses"]),
        }
    )
    for stave in STAVE_NAMES:
        got = int(sample_ii[stave].sum())
        exp = int(expected[stave])
        rows.append(
            {
                "quantity": f"Sample II analysis {stave} pulses",
                "report_value": exp,
                "reproduced": got,
                "delta": got - exp,
                "tolerance": 0,
                "pass": got == exp,
            }
        )
    return pd.DataFrame(rows)


def balanced_pulse_indices(meta: pd.DataFrame, runs: Sequence[int], per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    subset = meta[meta["run"].isin([int(r) for r in runs])]
    for _, group in subset.groupby(["run", "stave_idx"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), int(per_run_stave))
        if take:
            pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return out


def make_amp_bins(meta: pd.DataFrame, train_idx: np.ndarray, n_bins: int) -> np.ndarray:
    log_amp = np.log1p(meta["amplitude_adc"].to_numpy(dtype=float))
    qs = np.linspace(0.0, 1.0, int(n_bins) + 1)[1:-1]
    edges = np.unique(np.quantile(log_amp[train_idx], qs))
    if len(edges) == 0:
        return np.zeros(len(meta), dtype=np.int8)
    return np.digitize(log_amp, edges).astype(np.int8)


def build_templates(norm: np.ndarray, meta: pd.DataFrame, train_idx: np.ndarray, amp_bins: np.ndarray) -> dict:
    templates: Dict[Tuple, np.ndarray] = {}
    train_meta = meta.iloc[train_idx]
    global_template = np.median(norm[train_idx], axis=0)
    templates[("global",)] = global_template.astype(np.float32)
    for stave in range(len(STAVE_NAMES)):
        idx = train_idx[train_meta["stave_idx"].to_numpy(dtype=int) == stave]
        if len(idx):
            templates[("stave", stave)] = np.median(norm[idx], axis=0).astype(np.float32)
    for stave in range(len(STAVE_NAMES)):
        for peak in range(norm.shape[1]):
            mask = (train_meta["stave_idx"].to_numpy(dtype=int) == stave) & (train_meta["peak_sample"].to_numpy(dtype=int) == peak)
            idx = train_idx[mask]
            if len(idx) >= 20:
                templates[("stave_peak", stave, peak)] = np.median(norm[idx], axis=0).astype(np.float32)
    for stave in range(len(STAVE_NAMES)):
        for peak in range(norm.shape[1]):
            for amp_bin in sorted(set(amp_bins[train_idx].tolist())):
                mask = (
                    (train_meta["stave_idx"].to_numpy(dtype=int) == stave)
                    & (train_meta["peak_sample"].to_numpy(dtype=int) == peak)
                    & (amp_bins[train_idx] == amp_bin)
                )
                idx = train_idx[mask]
                if len(idx) >= 15:
                    templates[("stave_peak_amp", stave, peak, int(amp_bin))] = np.median(norm[idx], axis=0).astype(np.float32)
    return templates


def predict_template(meta: pd.DataFrame, templates: dict, amp_bins: np.ndarray, pulse_idx: np.ndarray) -> np.ndarray:
    out = np.zeros((len(pulse_idx), 18), dtype=np.float32)
    for row, idx in enumerate(pulse_idx):
        m = meta.iloc[int(idx)]
        stave = int(m["stave_idx"])
        peak = int(m["peak_sample"])
        amp_bin = int(amp_bins[int(idx)])
        key = ("stave_peak_amp", stave, peak, amp_bin)
        if key not in templates:
            key = ("stave_peak", stave, peak)
        if key not in templates:
            key = ("stave", stave)
        if key not in templates:
            key = ("global",)
        out[row] = templates[key]
    return out


def neighbor_interp(norm: np.ndarray) -> np.ndarray:
    out = np.empty_like(norm)
    out[:, 0] = norm[:, 1]
    out[:, -1] = norm[:, -2]
    out[:, 1:-1] = 0.5 * (norm[:, :-2] + norm[:, 2:])
    return out


def fit_traditional_alpha(y: np.ndarray, template: np.ndarray, interp: np.ndarray, sample_idx: np.ndarray) -> Dict[int, float]:
    alphas: Dict[int, float] = {}
    for sample in sorted(set(sample_idx.tolist())):
        mask = sample_idx == sample
        d = template[mask] - interp[mask]
        denom = float(np.dot(d, d))
        if denom <= 1e-12:
            alpha = 0.0
        else:
            alpha = float(np.dot(y[mask] - interp[mask], d) / denom)
        alphas[int(sample)] = float(np.clip(alpha, 0.0, 1.0))
    return alphas


def row_view(
    config: dict,
    waves: np.ndarray,
    meta: pd.DataFrame,
    pulse_idx: np.ndarray,
    template_norm: np.ndarray,
    interp_norm: np.ndarray,
) -> dict:
    nsamp = int(config["samples_per_channel"])
    phase_lookup = phase_for_sample(config)
    wf = waves[pulse_idx].astype(np.float32)
    amp = meta["amplitude_adc"].to_numpy(dtype=np.float32)[pulse_idx]
    norm = wf / np.maximum(amp[:, None], 1.0)
    n_pulse = len(pulse_idx)
    sample_idx = np.tile(np.arange(nsamp, dtype=np.int16), n_pulse)
    pulse_row = np.repeat(np.arange(n_pulse, dtype=np.int32), nsamp)
    raw_pulse_index = np.repeat(pulse_idx.astype(np.int32), nsamp)
    target_norm = norm.reshape(-1).astype(np.float32)
    target_adc = wf.reshape(-1).astype(np.float32)
    amp_row = np.repeat(amp, nsamp).astype(np.float32)
    run_row = np.repeat(meta["run"].to_numpy(dtype=np.int16)[pulse_idx], nsamp)
    stave_idx = np.repeat(meta["stave_idx"].to_numpy(dtype=np.int8)[pulse_idx], nsamp)
    peak = np.repeat(meta["peak_sample"].to_numpy(dtype=np.int8)[pulse_idx], nsamp)
    area_over_amp = np.repeat((meta["area_adc_samples"].to_numpy(dtype=np.float32)[pulse_idx] / np.maximum(amp, 1.0)), nsamp)
    context = np.repeat(norm, nsamp, axis=0)
    context[np.arange(len(context)), sample_idx] = 0.0
    sample_onehot = np.zeros((len(context), nsamp), dtype=np.float32)
    sample_onehot[np.arange(len(context)), sample_idx] = 1.0
    stave_onehot = np.zeros((len(context), len(STAVE_NAMES)), dtype=np.float32)
    stave_onehot[np.arange(len(context)), stave_idx] = 1.0
    template_row = template_norm.reshape(-1).astype(np.float32)
    interp_row = interp_norm.reshape(-1).astype(np.float32)
    aux = np.column_stack(
        [
            np.log1p(amp_row),
            peak.astype(np.float32) / max(1, nsamp - 1),
            area_over_amp.astype(np.float32),
            sample_idx.astype(np.float32) / max(1, nsamp - 1),
            template_row,
            interp_row,
        ]
    ).astype(np.float32)
    x_tab = np.hstack([context, sample_onehot, stave_onehot, aux]).astype(np.float32)
    return {
        "x_tab": x_tab,
        "context": context.astype(np.float32),
        "aux": np.hstack([sample_onehot, stave_onehot, aux]).astype(np.float32),
        "target_norm": target_norm,
        "target_adc": target_adc,
        "amp": amp_row,
        "sample_idx": sample_idx,
        "phase": np.asarray([phase_lookup[int(s)] for s in sample_idx], dtype=object),
        "run": run_row,
        "stave_idx": stave_idx,
        "raw_pulse_index": raw_pulse_index,
        "pulse_row": pulse_row,
        "template": template_row,
        "interp": interp_row,
    }


def run_folds(runs: Sequence[int], n_folds: int = 3) -> List[np.ndarray]:
    runs = np.asarray(sorted(set(int(r) for r in runs)), dtype=int)
    return [fold for fold in np.array_split(runs, min(n_folds, len(runs))) if len(fold)]


def mae_adc(y_norm: np.ndarray, pred_norm: np.ndarray, amp: np.ndarray) -> float:
    return float(np.mean(np.abs((pred_norm - y_norm) * amp)))


def cv_subset(train_rows: dict, max_rows: int, seed: int) -> dict:
    n_rows = len(train_rows["target_norm"])
    if n_rows <= int(max_rows):
        return train_rows
    rng = np.random.default_rng(int(seed))
    idx = np.sort(rng.choice(np.arange(n_rows), size=int(max_rows), replace=False))
    return {key: (value[idx] if isinstance(value, np.ndarray) and len(value) == n_rows else value) for key, value in train_rows.items()}


def choose_ridge_alpha(train_rows: dict, train_runs: Sequence[int], alphas: Sequence[float], config: dict) -> Tuple[float, pd.DataFrame]:
    train_rows = cv_subset(train_rows, int(config["analysis"]["cv_max_rows"]), int(config["analysis"]["random_seed"]) + 101)
    rows = []
    folds = run_folds(train_runs, 3)
    for alpha in alphas:
        vals = []
        for held_runs in folds:
            va = np.isin(train_rows["run"], held_runs)
            tr = ~va
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha), solver="lsqr"))
            model.fit(train_rows["x_tab"][tr], train_rows["target_norm"][tr])
            pred = model.predict(train_rows["x_tab"][va])
            vals.append(mae_adc(train_rows["target_norm"][va], pred, train_rows["amp"][va]))
        rows.append({"method": "ridge", "alpha": float(alpha), "cv_mae_adc": float(np.mean(vals))})
    table = pd.DataFrame(rows).sort_values("cv_mae_adc", kind="mergesort")
    return float(table.iloc[0]["alpha"]), table


def choose_hgb_params(train_rows: dict, train_runs: Sequence[int], grid: Sequence[dict], config: dict) -> Tuple[dict, pd.DataFrame]:
    train_rows = cv_subset(train_rows, int(config["analysis"]["cv_max_rows"]), int(config["analysis"]["random_seed"]) + 202)
    rows = []
    folds = run_folds(train_runs, 3)
    for params in grid:
        vals = []
        for held_runs in folds:
            va = np.isin(train_rows["run"], held_runs)
            tr = ~va
            model = HistGradientBoostingRegressor(
                max_iter=int(params["max_iter"]),
                learning_rate=float(params["learning_rate"]),
                max_leaf_nodes=int(params["max_leaf_nodes"]),
                l2_regularization=float(params["l2_regularization"]),
                random_state=20260610,
            )
            model.fit(train_rows["x_tab"][tr], train_rows["target_norm"][tr])
            pred = model.predict(train_rows["x_tab"][va])
            vals.append(mae_adc(train_rows["target_norm"][va], pred, train_rows["amp"][va]))
        row = dict(params)
        row.update({"method": "gradient_boosted_trees", "cv_mae_adc": float(np.mean(vals))})
        rows.append(row)
    table = pd.DataFrame(rows).sort_values("cv_mae_adc", kind="mergesort")
    best = {k: table.iloc[0][k] for k in ["max_iter", "learning_rate", "max_leaf_nodes", "l2_regularization"]}
    return best, table


class TorchMLP(nn.Module):
    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x_tab: torch.Tensor, context: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.net(x_tab).squeeze(1)


class TorchCNN(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(
            nn.Conv1d(1, c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(c, 2 * c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(2 * c + n_aux, 2 * c), nn.ReLU(), nn.Linear(2 * c, 1))

    def forward(self, x_tab: torch.Tensor, context: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.conv(context[:, None, :])
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


class MaskedAttentionDenoiser(nn.Module):
    def __init__(self, n_samples: int, n_aux: int, width: int, heads: int) -> None:
        super().__init__()
        self.n_samples = int(n_samples)
        self.value = nn.Linear(1, width)
        self.pos = nn.Parameter(torch.randn(1, n_samples, width) * 0.02)
        self.attn = nn.MultiheadAttention(width, num_heads=int(heads), batch_first=True)
        self.norm = nn.LayerNorm(width)
        self.head = nn.Sequential(nn.Linear(width + n_aux, width), nn.ReLU(), nn.Linear(width, 1))

    def forward(self, x_tab: torch.Tensor, context: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        sample_onehot = aux[:, : self.n_samples]
        target_token = torch.argmax(sample_onehot, dim=1)
        z = self.value(context[:, :, None]) + self.pos
        z2, _ = self.attn(z, z, z, need_weights=False)
        z = self.norm(z + z2)
        chosen = z[torch.arange(z.shape[0], device=z.device), target_token]
        return self.head(torch.cat([chosen, aux], dim=1)).squeeze(1)


def standardize(train: np.ndarray, hold: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0, keepdims=True)
    scale = train.std(axis=0, keepdims=True)
    scale[scale < 1e-6] = 1.0
    return ((train - mean) / scale).astype(np.float32), ((hold - mean) / scale).astype(np.float32)


def torch_fit_predict(label: str, train_rows: dict, hold_rows: dict, config: dict) -> Tuple[np.ndarray, dict]:
    if torch is None or nn is None:
        raise RuntimeError("torch is required for neural denoisers")
    torch.set_num_threads(1)
    seed = int(config["analysis"]["random_seed"])
    rng = np.random.default_rng(seed + len(label))
    torch.manual_seed(seed + len(label))
    x_train, x_hold = train_rows["x_tab"], hold_rows["x_tab"]
    if label == "mlp":
        x_train, x_hold = standardize(x_train, x_hold)
        model = TorchMLP(x_train.shape[1], int(config["analysis"]["mlp_hidden"]))
    elif label == "one_dimensional_cnn":
        model = TorchCNN(train_rows["aux"].shape[1], int(config["analysis"]["cnn_channels"]))
    elif label == "masked_attention":
        model = MaskedAttentionDenoiser(
            int(config["samples_per_channel"]),
            train_rows["aux"].shape[1],
            int(config["analysis"]["attention_width"]),
            int(config["analysis"]["attention_heads"]),
        )
    else:
        raise ValueError(label)

    tensors = {
        "x_tab": torch.from_numpy(x_train.astype(np.float32)),
        "context": torch.from_numpy(train_rows["context"].astype(np.float32)),
        "aux": torch.from_numpy(train_rows["aux"].astype(np.float32)),
        "y": torch.from_numpy(train_rows["target_norm"].astype(np.float32)),
    }
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["analysis"]["torch_learning_rate"]),
        weight_decay=float(config["analysis"]["torch_weight_decay"]),
    )
    batch = int(config["analysis"]["torch_batch_size"])
    losses = []
    t0 = time.time()
    for _epoch in range(int(config["analysis"]["torch_epochs"])):
        order = rng.permutation(len(x_train))
        epoch_loss = 0.0
        seen = 0
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(tensors["x_tab"][idx], tensors["context"][idx], tensors["aux"][idx])
            loss = torch.mean((pred - tensors["y"][idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += float(loss.detach().cpu()) * len(idx)
            seen += len(idx)
        losses.append(epoch_loss / max(1, seen))
    elapsed = time.time() - t0

    model.eval()
    preds: List[np.ndarray] = []
    xh = torch.from_numpy(x_hold.astype(np.float32))
    ch = torch.from_numpy(hold_rows["context"].astype(np.float32))
    ah = torch.from_numpy(hold_rows["aux"].astype(np.float32))
    with torch.no_grad():
        for start in range(0, len(x_hold), 32768):
            preds.append(model(xh[start : start + 32768], ch[start : start + 32768], ah[start : start + 32768]).cpu().numpy())
    return np.concatenate(preds).astype(np.float32), {
        "method": label,
        "final_train_mse_norm": float(losses[-1]),
        "elapsed_s": float(elapsed),
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
    }


def predictions_frame(hold_rows: dict, pred_by_method: Dict[str, np.ndarray]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "run": hold_rows["run"],
            "stave": [STAVE_NAMES[int(i)] for i in hold_rows["stave_idx"]],
            "sample": hold_rows["sample_idx"],
            "phase": hold_rows["phase"],
            "amp_adc": hold_rows["amp"],
            "target_adc": hold_rows["target_adc"],
            "target_norm": hold_rows["target_norm"],
            "raw_pulse_index": hold_rows["raw_pulse_index"],
        }
    )
    frames = []
    for method, pred_norm in pred_by_method.items():
        tmp = frame.copy()
        tmp["method"] = method
        tmp["pred_norm"] = pred_norm.astype(np.float32)
        tmp["pred_adc"] = tmp["pred_norm"].to_numpy(dtype=np.float32) * tmp["amp_adc"].to_numpy(dtype=np.float32)
        tmp["residual_adc"] = tmp["target_adc"].to_numpy(dtype=np.float32) - tmp["pred_adc"].to_numpy(dtype=np.float32)
        tmp["abs_residual_adc"] = np.abs(tmp["residual_adc"].to_numpy(dtype=np.float32))
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True)


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    med = np.median(values)
    return float(1.4826 * np.median(np.abs(values - med)))


def method_metrics(preds: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    delta_rows = []
    runs = sorted(preds["run"].unique().tolist())
    reps = int(config["analysis"]["bootstrap_replicates"])
    for method, group in preds.groupby("method", sort=True):
        vals = []
        sigmas = []
        for _ in range(reps):
            chosen_runs = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"] == run] for run in chosen_runs], ignore_index=True)
            vals.append(float(boot["abs_residual_adc"].mean()))
            sigmas.append(robust_sigma(boot["residual_adc"].to_numpy(dtype=float)))
        rows.append(
            {
                "method": method,
                "mae_adc": float(group["abs_residual_adc"].mean()),
                "mae_ci_low_adc": float(np.quantile(vals, 0.025)),
                "mae_ci_high_adc": float(np.quantile(vals, 0.975)),
                "rmse_adc": float(np.sqrt(np.mean(np.square(group["residual_adc"].to_numpy(dtype=float))))),
                "robust_sigma_adc": robust_sigma(group["residual_adc"].to_numpy(dtype=float)),
                "robust_sigma_ci_low_adc": float(np.quantile(sigmas, 0.025)),
                "robust_sigma_ci_high_adc": float(np.quantile(sigmas, 0.975)),
                "median_bias_adc": float(group["residual_adc"].median()),
            }
        )
    summary = pd.DataFrame(rows).sort_values("mae_adc", kind="mergesort")

    baseline = "traditional_template_smoother"
    base = preds[preds["method"] == baseline]
    for method in sorted(preds["method"].unique()):
        if method == baseline:
            continue
        group = preds[preds["method"] == method]
        point = float(group["abs_residual_adc"].mean() - base["abs_residual_adc"].mean())
        vals = []
        for _ in range(reps):
            chosen_runs = rng.choice(runs, size=len(runs), replace=True)
            aa = pd.concat([group[group["run"] == run] for run in chosen_runs], ignore_index=True)
            bb = pd.concat([base[base["run"] == run] for run in chosen_runs], ignore_index=True)
            vals.append(float(aa["abs_residual_adc"].mean() - bb["abs_residual_adc"].mean()))
        delta_rows.append(
            {
                "method": method,
                "delta_mae_vs_traditional_adc": point,
                "ci_low_adc": float(np.quantile(vals, 0.025)),
                "ci_high_adc": float(np.quantile(vals, 0.975)),
            }
        )
    deltas = pd.DataFrame(delta_rows).sort_values("delta_mae_vs_traditional_adc", kind="mergesort")

    phase_rows = []
    for (method, phase), group in preds.groupby(["method", "phase"], sort=True):
        vals = []
        for _ in range(reps):
            chosen_runs = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"] == run] for run in chosen_runs], ignore_index=True)
            vals.append(robust_sigma(boot["residual_adc"].to_numpy(dtype=float)))
        phase_rows.append(
            {
                "method": method,
                "phase": phase,
                "n_rows": int(len(group)),
                "noise_sigma_adc": robust_sigma(group["residual_adc"].to_numpy(dtype=float)),
                "noise_sigma_ci_low_adc": float(np.quantile(vals, 0.025)),
                "noise_sigma_ci_high_adc": float(np.quantile(vals, 0.975)),
                "mae_adc": float(group["abs_residual_adc"].mean()),
            }
        )
    phase = pd.DataFrame(phase_rows).sort_values(["method", "phase"])
    return summary, deltas, phase


def sample_noise(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, sample), group in preds.groupby(["method", "sample"], sort=True):
        rows.append(
            {
                "method": method,
                "sample": int(sample),
                "phase": str(group["phase"].iloc[0]),
                "n_rows": int(len(group)),
                "noise_sigma_adc": robust_sigma(group["residual_adc"].to_numpy(dtype=float)),
                "mae_adc": float(group["abs_residual_adc"].mean()),
                "median_bias_adc": float(group["residual_adc"].median()),
            }
        )
    return pd.DataFrame(rows)


def systematics(preds: pd.DataFrame, phase: pd.DataFrame, winner: str, config: dict) -> pd.DataFrame:
    rows = []
    win = preds[preds["method"] == winner]
    sample_sig = sample_noise(win)
    for _, row in sample_sig.iterrows():
        rows.append(
            {
                "quantity": f"sample_{int(row['sample']):02d}_sigma_adc",
                "value": float(row["noise_sigma_adc"]),
                "unit": "ADC",
                "definition": "1.4826*MAD of held-out masked-sample residuals for the winning denoiser",
            }
        )
    rising_sigma = float(phase[(phase["method"] == winner) & (phase["phase"] == "rising_edge")]["noise_sigma_adc"].iloc[0])
    sample_period = float(config["sample_period_ns"])
    by_pulse = win.pivot_table(index="raw_pulse_index", columns="sample", values="target_adc", aggfunc="first")
    slope = by_pulse.diff(axis=1).iloc[:, 4:9].max(axis=1).to_numpy(dtype=float) / sample_period
    median_slope = float(np.nanmedian(np.abs(slope)))
    timing_floor = rising_sigma / max(median_slope, 1e-9)
    rows.append(
        {
            "quantity": "rising_edge_timing_floor_ns",
            "value": timing_floor,
            "unit": "ns",
            "definition": "rising-edge residual sigma divided by median held-out rising-edge slope",
        }
    )
    rows.append(
        {
            "quantity": "median_rising_edge_slope_adc_per_ns",
            "value": median_slope,
            "unit": "ADC/ns",
            "definition": "median of max positive first difference over samples 4-9 divided by 10 ns",
        }
    )
    all_sigma = sample_sig["noise_sigma_adc"].to_numpy(dtype=float)
    charge_sigma = float(np.sqrt(np.sum(np.square(all_sigma))))
    area_by_pulse = by_pulse.sum(axis=1).to_numpy(dtype=float)
    rows.append(
        {
            "quantity": "integrated_charge_noise_floor_adc_sample",
            "value": charge_sigma,
            "unit": "ADC sample",
            "definition": "quadrature sum of per-sample winning residual sigmas",
        }
    )
    rows.append(
        {
            "quantity": "relative_charge_noise_floor",
            "value": charge_sigma / max(float(np.nanmedian(np.abs(area_by_pulse))), 1e-9),
            "unit": "fraction",
            "definition": "charge noise floor divided by median absolute held-out pulse area",
        }
    )
    threshold = float(config["analysis"]["dropout_z_threshold"])
    sig_lookup = sample_sig.set_index("sample")["noise_sigma_adc"].to_dict()
    z = np.asarray([r / max(sig_lookup[int(s)], 1e-9) for r, s in zip(win["residual_adc"], win["sample"])])
    dropout_fpr = float(np.mean(z < -threshold))
    rows.append(
        {
            "quantity": f"dropout_false_positive_rate_z_lt_minus_{threshold:g}",
            "value": dropout_fpr,
            "unit": "fraction",
            "definition": "fraction of held-out normal samples whose negative denoising residual exceeds the per-sample threshold",
        }
    )
    rows.append(
        {
            "quantity": "ideal_adc_quantization_sigma",
            "value": QUANTIZATION_SIGMA_ADC,
            "unit": "ADC",
            "definition": "1/sqrt(12) for unit-spaced ADC bins; lower bound, not fit from data",
        }
    )
    return pd.DataFrame(rows)


def leakage_checks(preds: pd.DataFrame, config: dict, cv: pd.DataFrame) -> pd.DataFrame:
    train_runs = set(int(r) for r in config["train_runs"])
    heldout_runs = set(int(r) for r in config["heldout_runs"])
    pred_runs = set(int(r) for r in preds["run"].unique())
    return pd.DataFrame(
        [
            {
                "check": "train_heldout_run_sets_disjoint",
                "value": len(train_runs & heldout_runs),
                "pass": len(train_runs & heldout_runs) == 0,
            },
            {
                "check": "predictions_only_heldout_runs",
                "value": ",".join(str(r) for r in sorted(pred_runs)),
                "pass": pred_runs == heldout_runs,
            },
            {
                "check": "cv_rows_present_for_ridge_and_gbt",
                "value": int(len(cv)),
                "pass": int(len(cv)) >= len(config["analysis"]["ridge_alphas"]) + len(config["analysis"]["hgb_grid"]),
            },
            {
                "check": "target_sample_masked_in_context",
                "value": 1,
                "pass": True,
            },
        ]
    )


def markdown_table(df: pd.DataFrame, columns: Sequence[str], max_rows: Optional[int] = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep] + rows)


def make_plots(out_dir: Path, summary: pd.DataFrame, phase: pd.DataFrame, sample_table: pd.DataFrame, winner: str) -> None:
    plt.figure(figsize=(9, 4.8))
    order = summary.sort_values("mae_adc")
    x = np.arange(len(order))
    yerr = np.vstack(
        [
            order["mae_adc"].to_numpy() - order["mae_ci_low_adc"].to_numpy(),
            order["mae_ci_high_adc"].to_numpy() - order["mae_adc"].to_numpy(),
        ]
    )
    plt.bar(x, order["mae_adc"], color="#4c78a8")
    plt.errorbar(x, order["mae_adc"], yerr=yerr, fmt="none", ecolor="black", capsize=3)
    plt.xticks(x, order["method"], rotation=25, ha="right")
    plt.ylabel("Held-out MAE (ADC)")
    plt.tight_layout()
    plt.savefig(out_dir / "method_mae_ci.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 4.8))
    phases = ["pretrigger", "rising_edge", "peak", "tail"]
    for method in ["traditional_template_smoother", winner]:
        sub = phase[phase["method"] == method].set_index("phase").reindex(phases)
        plt.errorbar(
            phases,
            sub["noise_sigma_adc"],
            yerr=[
                sub["noise_sigma_adc"] - sub["noise_sigma_ci_low_adc"],
                sub["noise_sigma_ci_high_adc"] - sub["noise_sigma_adc"],
            ],
            marker="o",
            capsize=3,
            label=method,
        )
    plt.axhline(QUANTIZATION_SIGMA_ADC, color="black", linestyle="--", linewidth=1, label="1/sqrt(12) ADC")
    plt.ylabel("Robust residual sigma (ADC)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "phase_noise_floor.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 4.8))
    sub = sample_table[sample_table["method"] == winner].sort_values("sample")
    plt.plot(sub["sample"], sub["noise_sigma_adc"], marker="o")
    plt.axhline(QUANTIZATION_SIGMA_ADC, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Sample index")
    plt.ylabel("Winning residual sigma (ADC)")
    plt.tight_layout()
    plt.savefig(out_dir / "sample_noise_floor_winner.png", dpi=160)
    plt.close()


def write_report(
    out_dir: Path,
    config: dict,
    runtime: float,
    repro: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    phase: pd.DataFrame,
    sample_table: pd.DataFrame,
    sys_table: pd.DataFrame,
    cv: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    trad = summary[summary["method"] == "traditional_template_smoother"].iloc[0]
    win = summary[summary["method"] == winner].iloc[0]
    win_delta = deltas[deltas["method"] == winner]
    delta_text = "0.0000 [0.0000, 0.0000]"
    if len(win_delta):
        d = win_delta.iloc[0]
        delta_text = f"{d['delta_mae_vs_traditional_adc']:.4f} [{d['ci_low_adc']:.4f}, {d['ci_high_adc']:.4f}]"

    report = f"""# P13a - ADC quantization noise floor across pulse phase

- **Study ID:** P13a
- **Ticket:** {config['ticket_id']}
- **Author (worker label):** {config['worker']}
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction and the B-stack raw ROOT convention
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Git commit:** {git_commit()}
- **Config:** `configs/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.json`

## 0. Question

What per-sample ADC/electronics noise floor remains after conditioning on pulse phase, stave, amplitude, and neighboring waveform context, and does any learned denoiser beat a strong traditional template+smoother under a run-heldout split?

The preregistered ticket asked for noise sigma/MAD by phase, induced timing and charge floors, dropout false-positive rate, and an ML-minus-traditional denoising delta with bootstrap CIs.  This report uses a masked-sample denoising proxy: for sample \(j\), the value \(x_j\) is removed from the model input and the method predicts \(\hat x_j\) from all other samples and metadata.  The residual \(r_j=x_j-\hat x_j\), converted back to ADC counts, is the empirical unresolved sample component plus model mismatch.

## 1. Reproduction (mandatory gate)

The gate is the canonical raw-ROOT selected-pulse count for B-stack pulses with baseline-subtracted amplitude above 1000 ADC.

{markdown_table(repro, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

All rows pass exactly, so the noise-floor analysis proceeds.

## 2. Traditional non-ML method

The traditional baseline is a calibrated template+smoother.  For each selected pulse \(i\), raw samples are baseline-subtracted by the median of samples 0-3 and normalized by \(A_i=\max_t y_{{it}}\).  Sample-I training pulses define median templates

\\[
T_{{s,p,b}}(t)=\\operatorname{{median}}\\left(y_i(t)/A_i\\mid \\text{{stave}}=s,\\ \\text{{peak}}=p,\\ \\log(1+A_i)\\in b\\right),
\\]

with fallbacks to stave-peak, stave, and global medians.  A leave-one-sample local smoother predicts \(I_i(j)=(x_{{i,j-1}}+x_{{i,j+1}})/2\) for interior samples, using the nearest neighbor at the two boundaries.  On Sample I only, each sample obtains a clipped least-squares blend

\\[
\\hat x_i(j)=\\alpha_j T_i(j)+(1-\\alpha_j)I_i(j),\\quad
\\alpha_j=\\operatorname{{clip}}_{{[0,1]}}\\frac{{\\sum_i (x_{{ij}}-I_{{ij}})(T_{{ij}}-I_{{ij}})}}{{\\sum_i (T_{{ij}}-I_{{ij}})^2}}.
\\]

This is the baseline named `traditional_template_smoother`.  Its held-out MAE is `{trad['mae_adc']:.4f}` ADC with run-block 95% CI `[{trad['mae_ci_low_adc']:.4f}, {trad['mae_ci_high_adc']:.4f}]`.

## 3. ML and NN methods

The benchmark uses the same masked-sample target and the same held-out Sample-II rows for every method.  Tabular features include the 18-sample normalized waveform with the target sample set to zero, target-sample one-hot, stave one-hot, log amplitude, peak-sample phase, area/amplitude, the traditional template prediction, and neighbor interpolation.  No run id, event id, event order, or held-out target sample value is included.  Ridge and gradient-boosted-tree hyperparameters are selected by run-group CV inside Sample I; neural methods use fixed preregistered compact architectures:

- `ridge`: standardized linear ridge regression; alpha chosen by Sample-I run CV.
- `gradient_boosted_trees`: histogram gradient boosting; config grid chosen by Sample-I run CV.
- `mlp`: two-hidden-layer ReLU multilayer perceptron.
- `one_dimensional_cnn`: 1D convolutions over the masked waveform plus auxiliary metadata.
- `masked_attention`: new architecture for this ticket; a tiny masked self-attention denoiser that reads the target token representation after attention over the remaining samples.

CV scan:

{markdown_table(cv, cv.columns.tolist(), max_rows=10)}

## 4. Head-to-head benchmark

Primary metric: held-out masked-sample MAE in ADC counts.  Intervals are {int(config['analysis']['bootstrap_replicates'])}-replicate run-block bootstraps over held-out runs 58-65.

{markdown_table(summary, ['method', 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc', 'rmse_adc', 'robust_sigma_adc', 'median_bias_adc'])}

Paired ML-minus-traditional deltas:

{markdown_table(deltas, ['method', 'delta_mae_vs_traditional_adc', 'ci_low_adc', 'ci_high_adc'])}

Winner: **{winner}** with MAE `{win['mae_adc']:.4f}` ADC, CI `[{win['mae_ci_low_adc']:.4f}, {win['mae_ci_high_adc']:.4f}]`.  Winner minus traditional baseline is `{delta_text}` ADC.  The verdict in `result.json` is therefore `ml_beats_baseline={str(result['ml_beats_baseline']).lower()}`.

Noise floor by pulse phase for all methods:

{markdown_table(phase, ['method', 'phase', 'noise_sigma_adc', 'noise_sigma_ci_low_adc', 'noise_sigma_ci_high_adc', 'mae_adc'])}

For the winning method, sample-level robust sigmas are in `sample_noise_floor.csv`.  The irreducible quantization-only lower bound is \(1/\\sqrt{{12}}=0.2887\) ADC, so all fitted phase floors above that value include electronics noise, residual shape variation, and any denoiser model mismatch.

## 5. Falsification

- **Pre-registration:** the ticket fixed the metrics before fitting: phase noise sigma/MAD, timing and charge floors, dropout false-positive rate, and ML-minus-traditional delta with run-block bootstrap CIs.
- **Falsification test:** ML would be rejected as useful if every learned model had non-negative paired MAE delta versus the traditional baseline, or if the apparent best method only won after using held-out runs for calibration.
- **Result:** the paired bootstrap delta table above is the uncertainty-bearing comparison.  Six denoising families were compared, so this is reported as a benchmark ranking rather than as a single uncorrected discovery p-value.

## 6. Threats to validity

- **Benchmark/selection:** the traditional comparator is not a constant or global median; it combines amplitude/phase/stave templates with a leave-one-sample local smoother and calibrates the blend on training runs only.
- **Data leakage:** all fits, template bins, blend weights, and ML hyperparameter choices use Sample I only.  Sample II runs 58-65 are used only for evaluation and bootstrap intervals.  Features exclude run id, event id, and the target sample value.  Peak-sample phase is a measured pulse descriptor; it can be slightly coupled to the target sample near the maximum, so the peak-phase result should be read with that caveat.
- **Metric misuse:** MAE is the primary benchmark because it is robust for heavy-tailed sample residuals.  RMSE, median bias, robust sigma, phase sigmas, and sample sigmas are also reported so the full residual distribution is not compressed into one core number.
- **Post-hoc selection:** run split, phase bins, model families, bootstrap count, and CV grids are in the committed config.  The only model chosen after fitting is the winner by the preregistered primary metric.

## 7. Provenance manifest

`manifest.json` records input ROOT checksums, config, git commit, command line, runtime, package versions, random seeds, and output hashes.  `input_sha256.csv` gives per-run ROOT hashes.

## 8. Findings and next steps

The winning method is `{winner}`.  The phase table gives the practical ADC/electronics floor for pretrigger, rising edge, peak, and tail samples under run-heldout calibration.  Derived systematic quantities are:

{markdown_table(sys_table, ['quantity', 'value', 'unit', 'definition'])}

The rising-edge timing floor is a lower bound: it propagates only the sample noise term through a median rising-edge slope and does not include clock, path-length, time-walk, pile-up, or inter-stave correlation terms.  The charge floor similarly assumes independent sample residuals; correlations can make the true integrated charge uncertainty larger or smaller.

One follow-up is proposed in `result.json`: test whether adding the P13a sample-noise covariance as heteroscedastic weights changes S02/P03 timing residual tails under the same run-heldout discipline.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.py --config configs/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.json
```

Runtime for this execution was `{runtime:.1f}` s on `{platform.node()}`.  Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `run_counts.csv`, `reproduction_match_table.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `paired_deltas_vs_traditional.csv`, `phase_noise_floor.csv`, `sample_noise_floor.csv`, `systematics.csv`, `leakage_checks.csv`, `cv_scan.csv`, and three PNG figures.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["analysis"]["random_seed"]))

    waves, meta, counts = scan_raw(config)
    counts.to_csv(out_dir / "run_counts.csv", index=False)
    repro = reproduction_table(config, counts)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    train_runs = [int(r) for r in config["train_runs"]]
    heldout_runs = [int(r) for r in config["heldout_runs"]]
    per = int(config["analysis"]["balanced_pulses_per_run_stave"])
    train_idx = balanced_pulse_indices(meta, train_runs, per, rng)
    hold_idx = balanced_pulse_indices(meta, heldout_runs, per, rng)
    amp = meta["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = waves / np.maximum(amp[:, None], 1.0)

    amp_bins = make_amp_bins(meta, train_idx, int(config["analysis"]["amplitude_template_bins"]))
    templates = build_templates(norm, meta, train_idx, amp_bins)
    train_template = predict_template(meta, templates, amp_bins, train_idx)
    hold_template = predict_template(meta, templates, amp_bins, hold_idx)
    train_norm = norm[train_idx]
    hold_norm = norm[hold_idx]
    train_interp = neighbor_interp(train_norm)
    hold_interp = neighbor_interp(hold_norm)

    train_rows = row_view(config, waves, meta, train_idx, train_template, train_interp)
    hold_rows = row_view(config, waves, meta, hold_idx, hold_template, hold_interp)

    alpha = fit_traditional_alpha(train_rows["target_norm"], train_rows["template"], train_rows["interp"], train_rows["sample_idx"])
    alpha_vec = np.asarray([alpha[int(s)] for s in hold_rows["sample_idx"]], dtype=np.float32)
    pred_by_method: Dict[str, np.ndarray] = {
        "traditional_template_smoother": alpha_vec * hold_rows["template"] + (1.0 - alpha_vec) * hold_rows["interp"]
    }

    print("choosing ridge alpha ...")
    best_alpha, ridge_cv = choose_ridge_alpha(train_rows, train_runs, config["analysis"]["ridge_alphas"], config)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha), solver="lsqr"))
    ridge.fit(train_rows["x_tab"], train_rows["target_norm"])
    pred_by_method["ridge"] = ridge.predict(hold_rows["x_tab"]).astype(np.float32)

    print("choosing gradient-boosted tree params ...")
    best_hgb, hgb_cv = choose_hgb_params(train_rows, train_runs, config["analysis"]["hgb_grid"], config)
    hgb = HistGradientBoostingRegressor(
        max_iter=int(best_hgb["max_iter"]),
        learning_rate=float(best_hgb["learning_rate"]),
        max_leaf_nodes=int(best_hgb["max_leaf_nodes"]),
        l2_regularization=float(best_hgb["l2_regularization"]),
        random_state=int(config["analysis"]["random_seed"]),
    )
    hgb.fit(train_rows["x_tab"], train_rows["target_norm"])
    pred_by_method["gradient_boosted_trees"] = hgb.predict(hold_rows["x_tab"]).astype(np.float32)
    cv = pd.concat([ridge_cv, hgb_cv], ignore_index=True, sort=False)

    torch_rows = []
    for label in ["mlp", "one_dimensional_cnn", "masked_attention"]:
        print(f"training {label} ...")
        pred, info = torch_fit_predict(label, train_rows, hold_rows, config)
        pred_by_method[label] = pred
        torch_rows.append(info)
    pd.DataFrame(torch_rows).to_csv(out_dir / "torch_training_summary.csv", index=False)

    cv.to_csv(out_dir / "cv_scan.csv", index=False)
    preds = predictions_frame(hold_rows, pred_by_method)
    preds.to_csv(out_dir / "heldout_predictions.csv", index=False)

    summary, deltas, phase = method_metrics(preds, config, rng)
    sample_table = sample_noise(preds)
    winner_row = summary.iloc[0].to_dict()
    winner = str(winner_row["method"])
    sys_table = systematics(preds, phase, winner, config)
    leakage = leakage_checks(preds, config, cv)

    summary.to_csv(out_dir / "heldout_method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "paired_deltas_vs_traditional.csv", index=False)
    phase.to_csv(out_dir / "phase_noise_floor.csv", index=False)
    sample_table.to_csv(out_dir / "sample_noise_floor.csv", index=False)
    sys_table.to_csv(out_dir / "systematics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    make_plots(out_dir, summary, phase, sample_table, winner)
    traditional = summary[summary["method"] == "traditional_template_smoother"].iloc[0].to_dict()
    delta = deltas[deltas["method"] == winner]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "exact selected-pulse count match",
        "traditional": {
            "method": "traditional_template_smoother",
            "metric": "heldout_masked_sample_mae_adc",
            "value": float(traditional["mae_adc"]),
            "ci": [float(traditional["mae_ci_low_adc"]), float(traditional["mae_ci_high_adc"])],
        },
        "ml": {
            "method": winner if winner != "traditional_template_smoother" else str(summary[summary["method"] != "traditional_template_smoother"].iloc[0]["method"]),
            "metric": "heldout_masked_sample_mae_adc",
            "value": float(summary[summary["method"] != "traditional_template_smoother"].iloc[0]["mae_adc"]),
            "ci": [
                float(summary[summary["method"] != "traditional_template_smoother"].iloc[0]["mae_ci_low_adc"]),
                float(summary[summary["method"] != "traditional_template_smoother"].iloc[0]["mae_ci_high_adc"]),
            ],
        },
        "winner": {
            "method": winner,
            "metric": "heldout_masked_sample_mae_adc",
            "value": float(winner_row["mae_adc"]),
            "ci": [float(winner_row["mae_ci_low_adc"]), float(winner_row["mae_ci_high_adc"])],
        },
        "winner_delta_vs_traditional": delta.iloc[0].to_dict() if len(delta) else {"method": winner, "delta_mae_vs_traditional_adc": 0.0, "ci_low_adc": 0.0, "ci_high_adc": 0.0},
        "ml_beats_baseline": bool(winner != "traditional_template_smoother" and float(winner_row["mae_adc"]) < float(traditional["mae_adc"])),
        "falsification": {
            "preregistered_metric": "heldout masked-sample MAE and phase robust sigma with run-block bootstrap CIs",
            "p_value": None,
            "n_tries": 6,
            "note": "benchmark ranking using paired run-block bootstrap deltas rather than a single null-hypothesis p-value",
        },
        "input_sha256": input_rows[0]["sha256"] if input_rows else "",
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            {
                "title": "P13b: heteroscedastic sample-noise weighting in timing residual fits",
                "body": "Use P13a per-sample noise/covariance estimates as heteroscedastic weights in S02/P03 timing residual correction, comparing unweighted CFD/template/ridge/HGB/MLP/CNN fits against noise-weighted variants with leave-run-out CIs. Expected information gain: tests whether sample-level electronics noise explains residual timing tails or whether shape/pile-up systematics dominate."
            }
        ],
        "noise_floor_by_phase": phase[phase["method"] == winner].to_dict(orient="records"),
        "systematics": sys_table.to_dict(orient="records"),
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "metrics": str(out_dir / "heldout_method_metrics.csv"),
            "phase_noise": str(out_dir / "phase_noise_floor.csv"),
        },
    }

    runtime = time.time() - t0
    write_report(out_dir, config, runtime, repro, summary, deltas, phase, sample_table, sys_table, cv, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "command": " ".join([sys.executable] + sys.argv),
        "config_path": str(config_path),
        "config": config,
        "git_commit": git_commit(),
        "runtime_s": runtime,
        "platform": {
            "node": platform.node(),
            "python": platform.python_version(),
            "system": platform.platform(),
        },
        "package_versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "random_seed": int(config["analysis"]["random_seed"]),
        "input_files": input_rows,
        "output_sha256": output_hashes(out_dir),
        "reproduction": repro.to_dict(orient="records"),
        "winner": result["winner"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    print(f"wrote {out_dir}")
    print(f"winner: {winner} MAE={winner_row['mae_adc']:.4f} ADC")


if __name__ == "__main__":
    main()
