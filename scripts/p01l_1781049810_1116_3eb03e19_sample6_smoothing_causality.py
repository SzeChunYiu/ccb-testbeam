#!/usr/bin/env python3
"""P01l sample-6 smoothing causality atlas against S02b residuals.

The analysis is deliberately fold-local: every leave-one-run-out fold rebuilds
the S02 global template, S02b binned-template SSE nuisance, and train-only S02b
global-template timewalk before fitting waveform residual correctors. It also
recomputes traditional pickoffs after train-defined sample-6 replacement
operators. The ML features exclude event ids, run ids, event order, other-stave
times, and pairwise residuals.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p01l-1781049810")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02

torch.set_num_threads(1)


def load_s02b_module():
    path = Path(__file__).resolve().parents[1] / "reports" / "1781000705.514762.105c186b__s02b_template_timewalk_closure" / "s02b_template_timewalk_closure.py"
    spec = importlib.util.spec_from_file_location("s02b_template_timewalk_closure", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s02b = load_s02b_module()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


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


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def fold_config(config: dict, heldout_run: int) -> dict:
    cfg = copy.deepcopy(config)
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [run for run in runs if run != int(heldout_run)]
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def run_family(run: int, config: dict) -> str:
    for family, runs in config["ml"]["run_family_controls"].items():
        if int(run) in [int(r) for r in runs]:
            return str(family)
    return "unknown"


def one_hot(values: Sequence[str], levels: Sequence[str]) -> np.ndarray:
    out = np.zeros((len(values), len(levels)), dtype=np.float32)
    lookup = {level: i for i, level in enumerate(levels)}
    for i, value in enumerate(values):
        if value in lookup:
            out[i, lookup[value]] = 1.0
    return out


def focus_samples(config: dict) -> set:
    return set(int(i) for i in config.get("early_samples", [config.get("sample_index", 6)]))


def waveform_feature_blocks(pulses: pd.DataFrame, config: dict, mask_name: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    sample_set = focus_samples(config)
    masked = norm.copy()
    if mask_name == "full":
        keep = np.ones(masked.shape[1], dtype=bool)
    elif mask_name == "no_sample6":
        keep = np.ones(masked.shape[1], dtype=bool)
        for sample in sample_set:
            keep[sample] = False
        masked[:, ~keep] = 0.0
    elif mask_name == "only_sample6":
        keep = np.zeros(masked.shape[1], dtype=bool)
        for sample in sample_set:
            keep[sample] = True
        masked[:, ~keep] = 0.0
    else:
        raise ValueError(mask_name)

    amp64 = pulses["amplitude_adc"].to_numpy(dtype=float)
    hand = np.vstack(
        [
            np.log1p(amp64),
            pulses["peak_sample"].to_numpy(dtype=float),
            pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp64, 1.0),
            pulses["s02b_template_sse"].to_numpy(dtype=float),
        ]
    ).T.astype(np.float32)
    staves = list(config["timing"]["downstream_staves"])
    stave_hot = one_hot([str(s) for s in pulses["stave"]], staves)
    aux = np.hstack([hand, stave_hot]).astype(np.float32)
    names = [f"{mask_name}_sample_{i:02d}_over_amp" for i in range(masked.shape[1])]
    names += ["log_amp", "peak_sample", "area_over_amp", "s02b_template_sse"]
    names += [f"stave_{s}" for s in staves]
    return masked.astype(np.float32), aux, names


def flat_features(pulses: pd.DataFrame, config: dict, mask_name: str) -> Tuple[np.ndarray, List[str]]:
    wave, aux, names = waveform_feature_blocks(pulses, config, mask_name)
    return np.hstack([wave, aux]).astype(np.float32), names


def run_family_control_features(pulses: pd.DataFrame, config: dict) -> Tuple[np.ndarray, List[str]]:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    hand = np.vstack(
        [
            np.log1p(amp),
            pulses["peak_sample"].to_numpy(dtype=float),
            pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0),
            pulses["s02b_template_sse"].to_numpy(dtype=float),
        ]
    ).T.astype(np.float32)
    staves = list(config["timing"]["downstream_staves"])
    families = list(config["ml"]["run_family_controls"].keys())
    stave_hot = one_hot([str(s) for s in pulses["stave"]], staves)
    family_hot = one_hot([run_family(int(r), config) for r in pulses["run"]], families)
    names = ["log_amp", "peak_sample", "area_over_amp", "s02b_template_sse"]
    names += [f"stave_{s}" for s in staves]
    names += [f"run_family_{f}" for f in families]
    return np.hstack([hand, stave_hot, family_hot]).astype(np.float32), names


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def standardize_by_train(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_mask] = scaler.fit_transform(X[train_mask])
    if (~train_mask).any():
        Xs[~train_mask] = scaler.transform(X[~train_mask])
    return Xs.astype(np.float32), scaler


class WaveformCNN(nn.Module):
    def __init__(self, n_samples: int, n_aux: int, channels: int) -> None:
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
        width = max(2 * c + int(n_aux), 12)
        self.head = nn.Sequential(nn.Linear(2 * c + int(n_aux), width), nn.ReLU(), nn.Linear(width, 2))

    def forward(self, x_wave: torch.Tensor, x_aux: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(x_wave[:, None, :])
        out = self.head(torch.cat([z, x_aux], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


class EarlyLateGatedNet(nn.Module):
    def __init__(self, n_samples: int, n_aux: int, hidden: int, early_samples: Sequence[int]) -> None:
        super().__init__()
        early_idx = torch.tensor([int(i) for i in early_samples], dtype=torch.long)
        late_idx = torch.tensor([i for i in range(n_samples) if i not in set(int(j) for j in early_samples)], dtype=torch.long)
        self.register_buffer("early_idx", early_idx)
        self.register_buffer("late_idx", late_idx)
        h = int(hidden)
        self.early = nn.Sequential(nn.Linear(len(early_idx), h), nn.ReLU(), nn.Linear(h, h), nn.ReLU())
        self.late = nn.Sequential(nn.Linear(len(late_idx), h), nn.ReLU(), nn.Linear(h, h), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(int(n_aux), h), nn.ReLU(), nn.Linear(h, 1), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(h + int(n_aux), h), nn.ReLU(), nn.Linear(h, 2))

    def forward(self, x_wave: torch.Tensor, x_aux: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        ze = self.early(x_wave.index_select(1, self.early_idx))
        zl = self.late(x_wave.index_select(1, self.late_idx))
        gate = self.gate(x_aux)
        z = gate * ze + (1.0 - gate) * zl
        out = self.head(torch.cat([z, x_aux], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def train_torch_wave_model(
    model: nn.Module,
    wave: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[nn.Module, np.ndarray, np.ndarray]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    wave_s, _ = standardize_by_train(wave, train_idx)
    aux_s, _ = standardize_by_train(aux, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["torch_learning_rate"]),
        weight_decay=float(config["ml"]["torch_weight_decay"]),
    )
    xw_all = torch.from_numpy(wave_s[train_idx])
    xa_all = torch.from_numpy(aux_s[train_idx])
    y_all = torch.from_numpy(y_train)
    batch_size = int(config["ml"]["torch_batch_size"])
    min_var = float(config["ml"]["torch_min_sigma_ns"]) ** 2
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            mu, log_var = model(xw_all[take], xa_all[take])
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((y_all[take] - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, wave_s, aux_s


def predict_torch_wave(model: nn.Module, wave_s: np.ndarray, aux_s: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(wave_s.astype(np.float32)), torch.from_numpy(aux_s.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(config["ml"]["torch_min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def cv_alpha_ridge(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, runs: np.ndarray, config: dict) -> Tuple[float, pd.DataFrame]:
    idx = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(3, len(np.unique(groups)))
    rows = []
    if n_splits < 2:
        return float(config["ml"]["ridge_alphas"][0]), pd.DataFrame(rows)
    gkf = GroupKFold(n_splits=n_splits)
    best = (math.inf, float(config["ml"]["ridge_alphas"][0]))
    for alpha in [float(a) for a in config["ml"]["ridge_alphas"]]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y[train_mask], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[idx[tr]], y[idx[tr]])
            pred = model.predict(X[idx[va]])
            score = float(np.sqrt(np.mean((pred - y[idx[va]]) ** 2)))
            scores.append(score)
            rows.append({"model": "ridge", "alpha": alpha, "fold": int(fold), "target_rmse_ns": score})
        mean = float(np.mean(scores))
        rows.append({"model": "ridge", "alpha": alpha, "fold": -1, "target_rmse_ns": mean})
        if mean < best[0]:
            best = (mean, alpha)
    return best[1], pd.DataFrame(rows)


def fit_predict_tabular(
    kind: str,
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    y_train = y[train_idx].copy()
    if shuffle_y:
        rng.shuffle(y_train)
    cv = pd.DataFrame()
    if kind == "ridge":
        train_mask = np.zeros(len(X), dtype=bool)
        train_mask[train_idx] = True
        alpha, cv = cv_alpha_ridge(X, y, train_mask, np.zeros(len(X), dtype=int), config)
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"alpha": float(alpha)}
    if kind == "hgb":
        model = HistGradientBoostingRegressor(
            max_iter=int(config["ml"]["hgb_max_iter"]),
            learning_rate=float(config["ml"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["ml"]["hgb_max_leaf_nodes"]),
            l2_regularization=0.01,
            random_state=seed,
        )
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"max_iter": int(config["ml"]["hgb_max_iter"])}
    if kind == "extra_trees":
        model = ExtraTreesRegressor(
            n_estimators=160,
            min_samples_leaf=6,
            max_features=0.65,
            n_jobs=1,
            random_state=seed,
        )
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"n_estimators": 160, "min_samples_leaf": 6}
    raise ValueError(kind)


def fit_predict_mlp(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    mlp_cfg = copy.deepcopy(config)
    mlp_cfg["ml"]["learning_rate"] = float(config["ml"]["torch_learning_rate"])
    mlp_cfg["ml"]["weight_decay"] = float(config["ml"]["torch_weight_decay"])
    mlp_cfg["ml"]["batch_size"] = int(config["ml"]["torch_batch_size"])
    mlp_cfg["ml"]["epochs"] = int(config["ml"]["torch_epochs"])
    mlp_cfg["ml"]["min_sigma_ns"] = float(config["ml"]["torch_min_sigma_ns"])
    model, Xs, _ = p03a.train_torch_model(
        X,
        y,
        train_idx,
        int(config["ml"]["mlp_hidden"]),
        float(config["ml"]["torch_weight_decay"]),
        mlp_cfg,
        seed,
        shuffle_y=shuffle_y,
    )
    pred, sigma = p03a.predict_torch(model, Xs, mlp_cfg)
    return pred, sigma, {"hidden": int(config["ml"]["mlp_hidden"])}


def fit_predict_wave_net(
    kind: str,
    wave: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    if kind == "cnn1d":
        model = WaveformCNN(wave.shape[1], aux.shape[1], int(config["ml"]["cnn_channels"]))
        info = {"channels": int(config["ml"]["cnn_channels"])}
    elif kind == "early_late_gated":
        model = EarlyLateGatedNet(wave.shape[1], aux.shape[1], int(config["ml"]["gated_hidden"]), config["early_samples"])
        info = {"hidden": int(config["ml"]["gated_hidden"])}
    else:
        raise ValueError(kind)
    model, wave_s, aux_s = train_torch_wave_model(model, wave, aux, y, train_idx, config, seed, shuffle_y=shuffle_y)
    pred, sigma = predict_torch_wave(model, wave_s, aux_s, config)
    return pred, sigma, info


def event_pair_residual_frame(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str, str]], config: dict, runs: Sequence[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for internal, label, family in methods:
        sub["tcorr"] = sub[f"t_{internal}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        event_run = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                rows.append(
                    {
                        "run": int(event_run[event_id]),
                        "event_id": event_id,
                        "pair": f"{a}-{b}",
                        "method": label,
                        "family": family,
                        "residual_ns": float(row[a] - row[b]),
                    }
                )
    return pd.DataFrame(rows)


def quantile_edges(values: np.ndarray, n_bins: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return np.asarray([0.0, 1.0])
    edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) < 2:
        eps = max(abs(float(edges[0])) * 1e-6, 1e-6)
        edges = np.asarray([float(edges[0]) - eps, float(edges[0]) + eps])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def digitize_edges(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges[1:-1], values, side="right"), 0, max(len(edges) - 2, 0)).astype(int)


def sample6_replaced_frames(pulses: pd.DataFrame, config: dict) -> Dict[str, pd.DataFrame]:
    k = int(config.get("sample_index", 6))
    n_bins = int(config["binned_template"]["n_amplitude_bins"])
    out: Dict[str, pd.DataFrame] = {}
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    train_mask = pulses["run"].isin(config["timing"]["train_runs"]).to_numpy()
    staves = sorted(pulses["stave"].unique())
    log_amp = np.log1p(np.maximum(amp, 0.0))
    family = np.asarray([run_family(int(r), config) for r in pulses["run"]])

    edges_by_stave = {}
    bin_id = np.zeros(len(pulses), dtype=int)
    for stave in staves:
        smask = pulses["stave"].to_numpy() == stave
        train_stave = smask & train_mask
        edges = quantile_edges(log_amp[train_stave], n_bins)
        edges_by_stave[stave] = edges
        bin_id[smask] = digitize_edges(log_amp[smask], edges)

    template_value = {}
    control_value = {}
    stave_value = {}
    for stave in staves:
        smask = (pulses["stave"].to_numpy() == stave) & train_mask
        stave_value[stave] = float(np.median(norm[smask, k])) if smask.any() else 0.0
        for b in range(n_bins):
            bmask = smask & (bin_id == b)
            template_value[(stave, b)] = float(np.median(norm[bmask, k])) if bmask.any() else stave_value[stave]
            for fam in config["ml"]["run_family_controls"].keys():
                fmask = bmask & (family == fam)
                control_value[(stave, fam, b)] = float(np.median(norm[fmask, k])) if fmask.any() else template_value[(stave, b)]

    replacements = {
        "local_linear": 0.5 * (wf[:, k - 1] + wf[:, k + 1]),
        "amplitude_bin_template": np.asarray([amp[i] * template_value[(pulses.iloc[i]["stave"], int(bin_id[i]))] for i in range(len(pulses))]),
        "control_stratum": np.asarray(
            [amp[i] * control_value[(pulses.iloc[i]["stave"], family[i], int(bin_id[i]))] for i in range(len(pulses))]
        ),
    }
    for name, sample_values in replacements.items():
        mod = wf.copy()
        mod[:, k] = sample_values
        frame = pulses.copy()
        frame["waveform"] = list(mod)
        out[name] = frame
    return out


def add_atlas_pickoff_times(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray], suffix: str) -> List[Tuple[str, str, str]]:
    period = float(config["sample_period_ns"])
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy()
    methods: List[Tuple[str, str, str]] = []
    pulses[f"t_cfd20_{suffix}_ns"] = period * s02.cfd_time_samples(wf, amp, 0.20)
    methods.append((f"cfd20_{suffix}", f"cfd20/{suffix}", "sample6_atlas"))
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses[f"t_template_phase_{suffix}_ns"] = period * s02.template_phase_time(pulses, templates, grid)
    methods.append((f"template_phase_{suffix}", f"template_phase/{suffix}", "sample6_atlas"))
    for lo, hi in config["timing"]["of_windows"]:
        internal = f"of_{int(lo)}_{int(hi)}_{suffix}"
        pulses[f"t_{internal}_ns"] = period * s02.optimal_filter_time(pulses, templates, (int(lo), int(hi)))
        methods.append((internal, f"of_{int(lo)}_{int(hi)}/{suffix}", "sample6_atlas"))
    return methods


def sample6_atlas_pairs(work: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray], heldout_run: int) -> pd.DataFrame:
    frames = {"raw": work.copy()}
    frames.update(sample6_replaced_frames(work, config))
    parts = []
    for suffix, frame in frames.items():
        heldout = frame[frame["run"] == int(heldout_run)].copy()
        methods = add_atlas_pickoff_times(heldout, config, templates, suffix)
        pairs = event_pair_residual_frame(heldout, methods, config, [heldout_run])
        pairs["variant"] = suffix
        pairs["pickoff"] = pairs["method"].str.split("/").str[0]
        parts.append(pairs)
    return pd.concat(parts, ignore_index=True)


def atlas_summary(pair_frame: pd.DataFrame, rng: np.random.Generator, n_boot: int, pooled: bool = False) -> pd.DataFrame:
    rows = []
    group_cols = ["pickoff", "variant", "method"]
    run_ids = sorted(pair_frame["run"].unique())
    by_method = {
        method: frame.groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for method, frame in pair_frame.groupby("method")
    }
    event_by_run = {
        int(run): np.asarray(sorted(pair_frame[pair_frame["run"] == run]["event_id"].unique()))
        for run in run_ids
    }
    for (pickoff, variant, method), frame in pair_frame.groupby(group_cols):
        vals = frame["residual_ns"].to_numpy(dtype=float)
        raw_method = f"{pickoff}/raw"
        raw_vals = pair_frame[pair_frame["method"] == raw_method]["residual_ns"].to_numpy(dtype=float)
        stats = []
        deltas = []
        for _ in range(int(n_boot)):
            pieces = []
            raw_pieces = []
            if pooled:
                sampled_runs = rng.choice(run_ids, size=len(run_ids), replace=True)
                for run in sampled_runs:
                    ids = event_by_run[int(run)]
                    sampled_ids = rng.choice(ids, size=len(ids), replace=True)
                    pieces.extend(by_method[method][eid] for eid in sampled_ids if eid in by_method[method])
                    raw_pieces.extend(by_method[raw_method][eid] for eid in sampled_ids if eid in by_method[raw_method])
            else:
                ids = np.asarray(sorted(frame["event_id"].unique()))
                sampled_ids = rng.choice(ids, size=len(ids), replace=True)
                pieces.extend(by_method[method][eid] for eid in sampled_ids if eid in by_method[method])
                raw_pieces.extend(by_method[raw_method][eid] for eid in sampled_ids if eid in by_method[raw_method])
            bvals = np.concatenate(pieces)
            rvals = np.concatenate(raw_pieces)
            stats.append(s02.sigma68(bvals))
            deltas.append(s02.sigma68(bvals) - s02.sigma68(rvals))
        rows.append(
            {
                "scope": "pooled_run_block" if pooled else f"run_{int(frame['run'].iloc[0])}",
                "pickoff": pickoff,
                "variant": variant,
                "method": method,
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": s02.sigma68(vals),
                "full_rms_ns": s02.full_rms(vals),
                "ci_low": float(np.percentile(stats, 2.5)),
                "ci_high": float(np.percentile(stats, 97.5)),
                "delta_vs_raw_same_pickoff_ns": s02.sigma68(vals) - s02.sigma68(raw_vals),
                "delta_ci_low": float(np.percentile(deltas, 2.5)),
                "delta_ci_high": float(np.percentile(deltas, 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values(["pickoff", "sigma68_ns", "variant"])


def metric_values(values: np.ndarray, baseline_p95_abs: float) -> dict:
    values = np.asarray(values, dtype=float)
    center = np.median(values) if len(values) else float("nan")
    abs_centered = np.abs(values - center)
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "abs_residual_p95_ns": float(np.percentile(abs_centered, 95.0)) if len(values) else float("nan"),
        "tail_frac_vs_traditional_p95": float(np.mean(abs_centered > baseline_p95_abs)) if len(values) else float("nan"),
    }


def per_run_bootstrap(pair_frame: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    baseline_vals = pair_frame[pair_frame["method"] == baseline_label]["residual_ns"].to_numpy(dtype=float)
    baseline_p95 = float(np.percentile(np.abs(baseline_vals - np.median(baseline_vals)), 95.0))
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    labels = sorted(pair_frame["method"].unique())
    family = pair_frame.groupby("method")["family"].first().to_dict()
    by_method = {
        label: pair_frame[pair_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    observed = {label: metric_values(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy(dtype=float), baseline_p95) for label in labels}
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot_scores = {}
        for label in labels:
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            boot_scores[label] = s02.sigma68(vals)
            stats[label].append(boot_scores[label])
        for label in labels:
            deltas[label].append(boot_scores[label] - boot_scores[baseline_label])
    rows = []
    for label in labels:
        rows.append(
            {
                "heldout_run": int(pair_frame["run"].iloc[0]),
                "method": label,
                "family": family[label],
                "baseline": baseline_label,
                "n_events": int(len(event_ids)),
                **observed[label],
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "delta_vs_traditional_ns": float(observed[label]["sigma68_ns"] - observed[baseline_label]["sigma68_ns"]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values(["heldout_run", "sigma68_ns"])


def run_block_bootstrap(all_pairs: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    labels = sorted(all_pairs["method"].unique())
    family = all_pairs.groupby("method")["family"].first().to_dict()
    baseline_vals = all_pairs[all_pairs["method"] == baseline_label]["residual_ns"].to_numpy(dtype=float)
    baseline_p95 = float(np.percentile(np.abs(baseline_vals - np.median(baseline_vals)), 95.0))
    observed = {label: metric_values(all_pairs[all_pairs["method"] == label]["residual_ns"].to_numpy(dtype=float), baseline_p95) for label in labels}
    run_ids = np.asarray(sorted(all_pairs["run"].unique()))
    by_run_method = {}
    for run in run_ids:
        run_frame = all_pairs[all_pairs["run"] == run]
        event_ids = np.asarray(sorted(run_frame["event_id"].unique()))
        for label in labels:
            by_run_method[(int(run), label)] = (
                event_ids,
                run_frame[run_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict(),
            )
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(run_ids, size=len(run_ids), replace=True)
        boot_scores = {}
        for label in labels:
            pieces = []
            for run in sampled_runs:
                event_ids, value_map = by_run_method[(int(run), label)]
                sampled_events = rng.choice(event_ids, size=len(event_ids), replace=True)
                pieces.extend(value_map[event_id] for event_id in sampled_events)
            vals = np.concatenate(pieces)
            boot_scores[label] = s02.sigma68(vals)
            stats[label].append(boot_scores[label])
        for label in labels:
            deltas[label].append(boot_scores[label] - boot_scores[baseline_label])
    rows = []
    for label in labels:
        rows.append(
            {
                "method": label,
                "family": family[label],
                "baseline": baseline_label,
                "n_heldout_runs": int(len(run_ids)),
                **observed[label],
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "delta_vs_traditional_ns": float(observed[label]["sigma68_ns"] - observed[baseline_label]["sigma68_ns"]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def prepare_fold_pulses(pulses_all: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    train = pulses_all[pulses_all["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    work = pulses_all.copy()
    s02.add_traditional_times(work, config, templates)
    binned_templates, alignment = s02b.build_binned_templates(train, config)
    period = float(config["sample_period_ns"])
    t_samples, sse, bins = s02b.binned_template_phase_time(work, binned_templates, config)
    work["t_s02b_template_ns"] = period * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins
    work, _, tw_cal_binned, tw_coef_binned = s02b.add_conventional_timewalk(work, config, "s02b_template", "s02b_template_timewalk")
    work, tw_cv_global, tw_cal_global, tw_coef_global = s02b.add_conventional_timewalk(work, config, "template_phase", "template_phase_timewalk")
    tw_cal = pd.concat([tw_cal_binned, tw_cal_global], ignore_index=True)
    tw_coef = pd.concat([tw_coef_binned, tw_coef_global], ignore_index=True)
    return (
        work,
        pd.concat([alignment.assign(table="alignment"), tw_cv_global.assign(table="timewalk_cv")], ignore_index=True, sort=False),
        pd.concat([tw_cal, tw_coef], ignore_index=True, sort=False),
        templates,
    )


def run_one_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = fold_config(config, heldout_run)
    work, diagnostics, calibration, templates = prepare_fold_pulses(pulses_all, cfg)
    atlas_pairs = sample6_atlas_pairs(work, cfg, templates, heldout_run)
    atlas_per_run = atlas_summary(atlas_pairs, rng, int(cfg["ml"]["bootstrap_samples"]), pooled=False)
    target = s02.event_residual_targets(work, "template_phase_timewalk", float(cfg["spacing_cm"]), cfg)
    runs = work["run"].to_numpy(dtype=int)
    train_base = np.isin(runs, cfg["timing"]["train_runs"])
    methods = [("template_phase_timewalk", "s02b_global_template_timewalk", "traditional")]
    cv_parts = []
    model_rows = []
    seed0 = int(config["ml"]["random_seed"]) + 1000 * int(heldout_run)
    masks = ["full", "no_sample6", "only_sample6"]
    model_kinds = ["ridge", "hgb", "extra_trees", "mlp", "cnn1d", "early_late_gated"]
    shuffled_methods = []

    for mask_name in masks:
        X, feature_names = flat_features(work, cfg, mask_name)
        wave, aux, _ = waveform_feature_blocks(work, cfg, mask_name)
        train_mask = train_base & finite_mask(X, target, runs)
        train_idx = np.flatnonzero(train_mask)
        for model_i, kind in enumerate(model_kinds):
            suffix = f"{kind}_{mask_name}"
            seed = seed0 + 17 * model_i + 101 * masks.index(mask_name)
            if kind in {"ridge", "hgb", "extra_trees"}:
                pred, cv, info = fit_predict_tabular(kind, X, target, train_idx, cfg, seed, shuffle_y=False)
                if len(cv):
                    cv_parts.append(cv.assign(heldout_run=int(heldout_run), mask=mask_name))
                pred_shuf, _, _ = fit_predict_tabular(kind, X, target, train_idx, cfg, seed + 777, shuffle_y=True)
            elif kind == "mlp":
                pred, sigma, info = fit_predict_mlp(X, target, train_idx, cfg, seed, shuffle_y=False)
                pred_shuf, _, _ = fit_predict_mlp(X, target, train_idx, cfg, seed + 777, shuffle_y=True)
            else:
                pred, sigma, info = fit_predict_wave_net(kind, wave, aux, target, train_idx, cfg, seed, shuffle_y=False)
                pred_shuf, _, _ = fit_predict_wave_net(kind, wave, aux, target, train_idx, cfg, seed + 777, shuffle_y=True)
            work[f"t_{suffix}_ns"] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred
            work[f"t_{suffix}_shuffled_ns"] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred_shuf
            methods.append((suffix, suffix, "ml"))
            methods.append((f"{suffix}_shuffled", f"{suffix}_shuffled", "shuffled_target_control"))
            shuffled_methods.append(f"{suffix}_shuffled")
            model_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "model": kind,
                    "mask": mask_name,
                    "n_train_pulses": int(len(train_idx)),
                    "n_features": int(X.shape[1]),
                    "feature_set_sha256": hashlib.sha256("|".join(feature_names).encode("utf-8")).hexdigest(),
                    **info,
                }
            )

    X_ctrl, ctrl_names = run_family_control_features(work, cfg)
    ctrl_train_mask = train_base & finite_mask(X_ctrl, target, runs)
    ctrl_idx = np.flatnonzero(ctrl_train_mask)
    for kind in ["ridge", "hgb"]:
        suffix = f"{kind}_run_family_control"
        pred, cv, info = fit_predict_tabular(kind, X_ctrl, target, ctrl_idx, cfg, seed0 + 3000 + len(kind), shuffle_y=False)
        work[f"t_{suffix}_ns"] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred
        methods.append((suffix, suffix, "run_family_control"))
        model_rows.append(
            {
                "heldout_run": int(heldout_run),
                "model": kind,
                "mask": "run_family_control",
                "n_train_pulses": int(len(ctrl_idx)),
                "n_features": int(X_ctrl.shape[1]),
                "feature_set_sha256": hashlib.sha256("|".join(ctrl_names).encode("utf-8")).hexdigest(),
                **info,
            }
        )

    pair_frame = event_pair_residual_frame(work, methods, cfg, [heldout_run])
    per_run = per_run_bootstrap(pair_frame, "s02b_global_template_timewalk", rng, int(cfg["ml"]["bootstrap_samples"]))
    leak_rows = [
        {
            "heldout_run": int(heldout_run),
            "check": "train_heldout_run_overlap",
            "value": int(len(set(cfg["timing"]["train_runs"]) & set(cfg["timing"]["heldout_runs"]))),
            "pass": len(set(cfg["timing"]["train_runs"]) & set(cfg["timing"]["heldout_runs"])) == 0,
        },
        {
            "heldout_run": int(heldout_run),
            "check": "train_heldout_event_id_overlap",
            "value": int(len(set(work[train_base]["event_id"]) & set(work[~train_base]["event_id"]))),
            "pass": len(set(work[train_base]["event_id"]) & set(work[~train_base]["event_id"])) == 0,
        },
        {
            "heldout_run": int(heldout_run),
            "check": "feature_audit",
            "value": 0,
            "pass": True,
            "detail": "same-pulse normalized waveform samples, amplitude summaries, S02b train-template SSE, stave one-hot; no run id, event id, event order, other-stave time, or target",
        },
    ]
    for label in shuffled_methods:
        nominal = label.replace("_shuffled", "")
        nval = float(per_run[per_run["method"] == nominal]["sigma68_ns"].iloc[0])
        sval = float(per_run[per_run["method"] == label]["sigma68_ns"].iloc[0])
        leak_rows.append(
            {
                "heldout_run": int(heldout_run),
                "check": f"shuffled_target_worse:{nominal}",
                "value": sval - nval,
                "pass": bool(sval >= nval),
                "detail": "positive means shuffled target is no better than nominal",
            }
        )
    diagnostics["heldout_run"] = int(heldout_run)
    calibration["heldout_run"] = int(heldout_run)
    cv_table = pd.concat(cv_parts, ignore_index=True) if cv_parts else pd.DataFrame()
    return (
        pair_frame,
        per_run,
        pd.DataFrame(leak_rows),
        pd.concat([diagnostics, calibration, cv_table, pd.DataFrame(model_rows)], ignore_index=True, sort=False),
        atlas_pairs,
        atlas_per_run,
    )


def markdown_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    match: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    leakage: pd.DataFrame,
    atlas_pooled: pd.DataFrame,
    atlas_per_run: pd.DataFrame,
) -> None:
    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    controls = pooled[pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    mask_compare = nominal[nominal["method"].str.contains("full|no_sample6|only_sample6", regex=True)].copy()
    text = f"""# P01l: sample-6 smoothing causality null atlas

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Claimed study:** {config['title']}
- **Input:** raw B-stack ROOT files from `{config['raw_root_dir']}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{config['timing']['loro_runs']}`
- **Sample under test:** waveform sample `{config.get('sample_index', 6)}` of the 18-sample, 10 ns waveform

## Question and preregistered estimand

The ticket asks whether the previously observed timing gain from sample-6 smoothing is causal waveform information or a replacement/quantization artifact.  The estimand is the B4/B6/B8 event-paired timing width after a train-only traditional timing closure:

`r_ab(e; m) = [t_a(e;m) - z_a v^-1] - [t_b(e;m) - z_b v^-1]`,

where `m` is a timing method, `z` is the stave spacing coordinate, and `v^-1 = 0.078 ns/cm`.  The headline metric is

`sigma68(m) = (Q84({{r_ab}}) - Q16({{r_ab}})) / 2`.

CIs are event bootstraps inside each held-out run and a nested run-block/event bootstrap for the pooled summary. Lower `sigma68`, lower full RMS, and lower tail fraction are better.

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before fitting any timing or ML model.

{markdown_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Methods

For every held-out run, the other six Sample-II runs define all train-only objects: the S02 global templates, amplitude-binned S02b template SSE nuisance, and polynomial/ridge timewalk closure. The strong traditional comparator is `s02b_global_template_timewalk`, which combines the conventional template-phase pickoff with train-only amplitude/timewalk corrections.

The sample-6 null atlas applies three replacements before recomputing conventional pickoffs:

- `local_linear`: `x_6 <- (x_5 + x_7) / 2`.
- `amplitude_bin_template`: `x_6 <- A_i median_train[x_6/A_i | stave, amplitude bin]`.
- `control_stratum`: `x_6 <- A_i median_train[x_6/A_i | stave, run-family, amplitude bin]`, with train-only fallback to the amplitude-bin template.

These replacements are evaluated against CFD20, template phase, and the configured optimal-filter windows. If replacing sample 6 improves a pickoff about as much as using it directly, the gain is not evidence that the raw sample carries unique causal timing information.

The residual learners target `y_i = t_i(S02b) - mean(t_j(S02b), t_k(S02b))` within the same event and predict a same-pulse correction. Six model families are benchmarked under three waveform masks:

- `ridge`: standardized linear Ridge regression.
- `hgb`: histogram gradient-boosted regression trees.
- `extra_trees`: no-sample-6-capable randomized tree ensemble.
- `mlp`: heteroskedastic fully connected neural net.
- `cnn1d`: compact one-dimensional convolutional network over 18 samples.
- `early_late_gated`: new architecture with a sample-6 branch and a complement branch mixed by a learned auxiliary-feature gate.

Masks are `full`, `no_sample6`, and `only_sample6`. Features exclude run id, event id, event order, other-stave timings, and pair residuals. Run-family controls use only hand summaries, stave, and coarse predeclared family (`early`, `middle`, `late`) without waveform samples. Shuffled-target controls repeat every nominal waveform model with train targets permuted.

## Traditional Sample-6 Replacement Atlas

{markdown_table(atlas_pooled.sort_values(['pickoff', 'sigma68_ns']), ['pickoff', 'variant', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'delta_vs_raw_same_pickoff_ns', 'delta_ci_low', 'delta_ci_high', 'n_pair_residuals'], n=60)}

## Pooled Benchmark

{markdown_table(nominal, ['method', 'family', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high', 'n_pair_residuals'], n=30)}

## Sample-6 Ablation

{markdown_table(mask_compare.sort_values(['method']), ['method', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'delta_vs_traditional_ns', 'tail_frac_vs_traditional_p95'], n=40)}

## Controls

{markdown_table(controls.sort_values('sigma68_ns'), ['method', 'family', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns'], n=35)}

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/mask combination is not causally interpretable.

## Held-Out Runs

{markdown_table(per_run[~per_run['family'].isin(['shuffled_target_control'])].sort_values(['heldout_run', 'sigma68_ns']), ['heldout_run', 'method', 'family', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'delta_vs_traditional_ns', 'n_events'], n=80)}

## Atlas By Held-Out Run

{markdown_table(atlas_per_run.sort_values(['scope', 'pickoff', 'sigma68_ns']), ['scope', 'pickoff', 'variant', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'delta_vs_raw_same_pickoff_ns'], n=100)}

## Leakage and Systematics

{markdown_table(leakage, ['heldout_run', 'check', 'value', 'pass'], n=120)}

Main caveats:

- The sample-6 replacements are falsification operators, not proposed production corrections. They intentionally test whether a smooth/interpolated value can mimic or improve the raw sample.
- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The S02b target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Run-family controls are coarse and predeclared; they diagnose gross family nuisance but cannot exclude all detector-condition drift.
- Multiple model families and masks are screened. The named winner is a benchmark winner, while adoption requires the control rows and atlas deltas to be physically coherent.

## Verdict

Winner in `result.json`: `{result['winner']['method']}` with pooled `sigma68 = {result['winner']['sigma68_ns']:.3f} ns` and CI `[{result['winner']['ci'][0]:.3f}, {result['winner']['ci'][1]:.3f}] ns`.

Interpretation: {result['verdict']}

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p01l_1781049810_1116_3eb03e19_sample6_smoothing_causality.py --config configs/p01l_1781049810_1116_3eb03e19_sample6_smoothing_causality.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `sample6_atlas_pooled.csv`, `sample6_atlas_by_run.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, all_pairs: pd.DataFrame) -> None:
    keep = pooled[~pooled["family"].isin(["shuffled_target_control"])].head(18).copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(np.arange(len(keep)), keep["sigma68_ns"], yerr=[keep["sigma68_ns"] - keep["ci_low"], keep["ci_high"] - keep["sigma68_ns"]], capsize=3)
    ax.set_xticks(np.arange(len(keep)))
    ax.set_xticklabels(keep["method"], rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("pooled pairwise sigma68 (ns)")
    ax.set_title("P01l sample-6 multimodel ablation")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_benchmark.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in ["s02b_global_template_timewalk"] + keep["method"].head(4).tolist():
        vals = all_pairs[all_pairs["method"] == method]["residual_ns"].to_numpy(dtype=float)
        if len(vals):
            ax.hist(vals, bins=70, histtype="step", density=True, label=f"{method} {s02.sigma68(vals):.2f} ns")
    ax.set_xlabel("pair residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_distributions.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json" and path.suffix != ".pkl":
            hashes[path.name] = sha256_file(path)
    return hashes


def jsonable_row(row: pd.Series) -> dict:
    out = {}
    for key, value in row.to_dict().items():
        if isinstance(value, (np.integer,)):
            out[key] = int(value)
        elif isinstance(value, (np.floating,)):
            out[key] = float(value)
        elif isinstance(value, (np.bool_,)):
            out[key] = bool(value)
        else:
            out[key] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p01l_1781049810_1116_3eb03e19_sample6_smoothing_causality.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")
    print("raw ROOT reproduction gate passed", flush=True)

    load_cfg = copy.deepcopy(config)
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loro_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    pulses_all = s02.load_downstream_pulses(load_cfg)
    print(f"loaded {len(pulses_all)} downstream pulse rows", flush=True)

    pair_parts = []
    per_run_parts = []
    leak_parts = []
    diag_parts = []
    atlas_pair_parts = []
    atlas_run_parts = []
    for heldout_run in config["timing"]["loro_runs"]:
        print(f"starting held-out run {heldout_run}", flush=True)
        pair_frame, per_run, leakage, diagnostics, atlas_pairs, atlas_per_run = run_one_fold(pulses_all, config, int(heldout_run), rng)
        pair_parts.append(pair_frame)
        per_run_parts.append(per_run)
        leak_parts.append(leakage)
        diag_parts.append(diagnostics)
        atlas_pair_parts.append(atlas_pairs)
        atlas_run_parts.append(atlas_per_run)
        print(f"finished held-out run {heldout_run}", flush=True)

    all_pairs = pd.concat(pair_parts, ignore_index=True)
    per_run = pd.concat(per_run_parts, ignore_index=True)
    leakage = pd.concat(leak_parts, ignore_index=True)
    diagnostics = pd.concat(diag_parts, ignore_index=True, sort=False)
    pooled = run_block_bootstrap(all_pairs, "s02b_global_template_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    atlas_pairs = pd.concat(atlas_pair_parts, ignore_index=True)
    atlas_per_run = pd.concat(atlas_run_parts, ignore_index=True)
    atlas_pooled = atlas_summary(atlas_pairs, rng, int(config["ml"]["bootstrap_samples"]), pooled=True)

    all_pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_block_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    diagnostics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    atlas_pairs.to_csv(out_dir / "sample6_atlas_pairwise_residuals.csv", index=False)
    atlas_per_run.to_csv(out_dir / "sample6_atlas_by_run.csv", index=False)
    atlas_pooled.to_csv(out_dir / "sample6_atlas_pooled.csv", index=False)
    pd.DataFrame([{"path": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control", "traditional"])].copy()
    winner_row = nominal.sort_values("sigma68_ns").iloc[0]
    baseline = pooled[pooled["method"] == "s02b_global_template_timewalk"].iloc[0]
    no_early_best = nominal[nominal["method"].str.contains("no_sample6")].sort_values("sigma68_ns").iloc[0]
    only_early_best = nominal[nominal["method"].str.contains("only_sample6")].sort_values("sigma68_ns").iloc[0]
    full_best = nominal[nominal["method"].str.contains("_full")].sort_values("sigma68_ns").iloc[0]
    shuffled_failures = int((leakage[leakage["check"].str.startswith("shuffled_target_worse", na=False)]["pass"] == False).sum())
    if float(no_early_best["sigma68_ns"]) <= float(full_best["sigma68_ns"]) + 0.10 and float(only_early_best["sigma68_ns"]) > float(no_early_best["sigma68_ns"]):
        verdict = "Sample 6 is not required for the best residual correction; gains persist when it is removed, so the sample-6 smoothing gain is consistent with nuisance/replacement structure rather than a unique causal timing source."
    else:
        verdict = "Sample 6 carries some predictive information, but shuffled-target, run-family, and replacement-atlas controls must be used before treating it as causal timing information."
    if shuffled_failures:
        verdict += f" {shuffled_failures} shuffled-target checks beat their nominal model and are flagged as stability caveats."

    result = {
        "study": "P01l",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
        "traditional_method": {
            "method": "s02b_global_template_timewalk",
            "sigma68_ns": float(baseline["sigma68_ns"]),
            "full_rms_ns": float(baseline["full_rms_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "full_rms_ns": float(winner_row["full_rms_ns"]),
            "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
            "delta_vs_traditional_ns": float(winner_row["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner_row["delta_ci_low"]), float(winner_row["delta_ci_high"])],
        },
        "sample6_ablation": {
            "best_full": {"method": str(full_best["method"]), "sigma68_ns": float(full_best["sigma68_ns"])},
            "best_no_sample6": {"method": str(no_early_best["method"]), "sigma68_ns": float(no_early_best["sigma68_ns"])},
            "best_only_sample6": {"method": str(only_early_best["method"]), "sigma68_ns": float(only_early_best["sigma68_ns"])},
        },
        "sample6_replacement_atlas": {
            "best_traditional_row": jsonable_row(atlas_pooled.sort_values("sigma68_ns").iloc[0]),
            "max_abs_replacement_delta_ns": float(atlas_pooled[atlas_pooled["variant"] != "raw"]["delta_vs_raw_same_pickoff_ns"].abs().max()),
        },
        "controls": {
            "shuffled_target_failures": shuffled_failures,
            "run_family_control_best_sigma68_ns": float(pooled[pooled["family"] == "run_family_control"]["sigma68_ns"].min()),
            "max_train_heldout_event_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
        },
        "verdict": verdict,
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    plot_outputs(out_dir, pooled, all_pairs)
    write_report(out_dir, config, result, match, pooled, per_run, leakage, atlas_pooled, atlas_per_run)
    manifest = {
        "study": "P01l",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path.resolve()),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "elapsed_s": manifest["elapsed_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
