#!/usr/bin/env python3
"""S14h: range and stopping-stave reconstruction from GEANT4 Sci_bar truth."""

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
from sklearn.metrics import accuracy_score, mean_absolute_error
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
PDG_LABELS = {
    11: "electron",
    22: "gamma",
    2112: "neutron",
    2212: "proton",
    1000010020: "deuteron",
    1000010030: "triton",
    1000020030: "helium3",
    1000020040: "alpha",
}


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


def pick_root(config: dict) -> Path:
    primary = Path(config["geant4_root"])
    if primary.exists():
        return primary
    fallback = Path(config["fallback_geant4_root"])
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"neither {primary} nor {fallback} exists")


def species_label(pdg: int) -> str:
    return PDG_LABELS.get(int(pdg), str(int(pdg)))


def iter_tree(tree: uproot.behaviors.TTree.TTree, branches: List[str], step_size: int) -> Iterable[ak.Array]:
    yield from tree.iterate(branches, step_size=step_size, library="ak")


def aggregate_events(config: dict, root_file: Path) -> Tuple[pd.DataFrame, np.ndarray, dict]:
    tree = uproot.open(root_file)[config["tree"]]
    entries = int(tree.num_entries)
    n_layers = int(config["layer_max"]) - int(config["layer_min"]) + 1
    branches = [
        "PrimaryPDG",
        "PrimaryEkin",
        "Sci_bar_LayerID",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_GlobalPosition_Z",
    ]
    rows: List[pd.DataFrame] = []
    vectors: List[np.ndarray] = []
    counts = {
        "tree_entries": entries,
        "events_with_sci_bar": 0,
        "sci_bar_hits": 0,
        "positive_sci_bar_hits": 0,
    }
    start_entry = 0
    truth_min = float(config["truth_min_edep_mev"])
    pseudo_run_size = int(config["pseudo_run_size"])
    layer_min = int(config["layer_min"])
    layer_max = int(config["layer_max"])
    spacing = float(config["layer_spacing_cm"])

    for batch in iter_tree(tree, branches, step_size=50000):
        n = len(batch["Sci_bar_EDep"])
        edep_by_layer = np.zeros((n, n_layers), dtype=np.float32)
        hit_count_by_layer = np.zeros((n, n_layers), dtype=np.float32)
        first_time_by_layer = np.full((n, n_layers), np.nan, dtype=np.float32)
        z_weighted_sum = np.zeros((n, n_layers), dtype=np.float64)
        pdg_edep: List[Dict[int, float]] = []
        stop_layer = np.full(n, -1, dtype=np.int16)
        n_pos_hits = np.zeros(n, dtype=np.int16)
        primary_proton_ekin = np.full(n, np.nan, dtype=np.float32)
        primary_deuteron_ekin = np.full(n, np.nan, dtype=np.float32)

        primary_pdg = ak.to_list(batch["PrimaryPDG"])
        primary_ekin = ak.to_list(batch["PrimaryEkin"])
        layers = ak.to_list(batch["Sci_bar_LayerID"])
        pdgs = ak.to_list(batch["Sci_bar_PDG"])
        edeps = ak.to_list(batch["Sci_bar_EDep"])
        times = ak.to_list(batch["Sci_bar_Time"])
        zs = ak.to_list(batch["Sci_bar_GlobalPosition_Z"])

        for i in range(n):
            for pdg, ekin in zip(primary_pdg[i], primary_ekin[i]):
                if int(pdg) == 2212:
                    primary_proton_ekin[i] = float(ekin)
                elif int(pdg) == 1000010020:
                    primary_deuteron_ekin[i] = float(ekin)

            species_totals: Dict[int, float] = {}
            deepest = -1
            for layer, pdg, edep, t, z in zip(layers[i], pdgs[i], edeps[i], times[i], zs[i]):
                layer_i = int(layer)
                edep_f = float(edep)
                counts["sci_bar_hits"] += 1
                if not (layer_min <= layer_i <= layer_max) or edep_f <= truth_min:
                    continue
                j = layer_i - layer_min
                edep_by_layer[i, j] += edep_f
                hit_count_by_layer[i, j] += 1.0
                if math.isnan(float(first_time_by_layer[i, j])) or float(t) < float(first_time_by_layer[i, j]):
                    first_time_by_layer[i, j] = float(t)
                z_weighted_sum[i, j] += edep_f * float(z)
                species_totals[int(pdg)] = species_totals.get(int(pdg), 0.0) + edep_f
                deepest = max(deepest, layer_i)
                n_pos_hits[i] += 1
                counts["positive_sci_bar_hits"] += 1
            stop_layer[i] = deepest
            pdg_edep.append(species_totals)

        has_sci = stop_layer >= 0
        counts["events_with_sci_bar"] += int(has_sci.sum())
        event_id = np.arange(start_entry, start_entry + n, dtype=np.int64)
        pseudo_run = event_id // pseudo_run_size
        total_edep = edep_by_layer.sum(axis=1)
        front_deltae = edep_by_layer[:, 0]
        residual_e = edep_by_layer[:, 1:].sum(axis=1)
        stopping_depth = stop_layer.astype(np.float32) * spacing
        residual_range = (layer_max - stop_layer).astype(np.float32) * spacing
        z_centroid = np.divide(
            z_weighted_sum.sum(axis=1),
            np.maximum(total_edep.astype(np.float64), 1e-12),
            out=np.full(n, np.nan, dtype=np.float64),
            where=total_edep > 0,
        )
        dominant_pdg = np.full(n, 0, dtype=np.int64)
        dominant_edep = np.zeros(n, dtype=np.float32)
        for i, totals in enumerate(pdg_edep):
            if totals:
                pdg, value = max(totals.items(), key=lambda kv: kv[1])
                dominant_pdg[i] = int(pdg)
                dominant_edep[i] = float(value)

        time_filled = np.nan_to_num(first_time_by_layer, nan=0.0, posinf=0.0, neginf=0.0)
        z_by_layer = np.divide(
            z_weighted_sum,
            np.maximum(edep_by_layer.astype(np.float64), 1e-12),
            out=np.zeros_like(z_weighted_sum),
            where=edep_by_layer > 0,
        ).astype(np.float32)
        seq = np.stack(
            [
                np.log1p(edep_by_layer),
                np.log1p(hit_count_by_layer),
                np.where(edep_by_layer > 0, 1.0, 0.0).astype(np.float32),
                time_filled / 100.0,
                z_by_layer / 100.0,
            ],
            axis=1,
        )

        rows.append(
            pd.DataFrame(
                {
                    "event_id": event_id[has_sci],
                    "pseudo_run": pseudo_run[has_sci].astype(int),
                    "true_stop_layer": stop_layer[has_sci].astype(int),
                    "stopping_depth_cm": stopping_depth[has_sci],
                    "residual_range_cm": residual_range[has_sci],
                    "n_positive_hits": n_pos_hits[has_sci].astype(int),
                    "total_edep_mev": total_edep[has_sci],
                    "front_deltae_mev": front_deltae[has_sci],
                    "residual_e_mev": residual_e[has_sci],
                    "z_centroid_cm": z_centroid[has_sci],
                    "dominant_sci_pdg": dominant_pdg[has_sci],
                    "dominant_sci_species": [species_label(x) for x in dominant_pdg[has_sci]],
                    "dominant_sci_edep_mev": dominant_edep[has_sci],
                    "primary_proton_ekin_mev": primary_proton_ekin[has_sci],
                    "primary_deuteron_ekin_mev": primary_deuteron_ekin[has_sci],
                }
            )
        )
        vectors.append(seq[has_sci])
        start_entry += n

    events = pd.concat(rows, ignore_index=True)
    wave = np.vstack(vectors).astype(np.float32)
    counts["accepted_fraction"] = float(len(events) / max(entries, 1))
    counts["n_pseudo_runs"] = int(events["pseudo_run"].nunique())
    return events, wave, counts


def tabular_features(events: pd.DataFrame, wave: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    edep = np.expm1(wave[:, 0, :])
    hits = np.expm1(wave[:, 1, :])
    present = wave[:, 2, :]
    total = np.maximum(edep.sum(axis=1), 1e-9)
    cumfrac = np.cumsum(edep, axis=1) / total[:, None]
    center = (edep * np.arange(edep.shape[1], dtype=np.float32)[None, :]).sum(axis=1) / total
    spread = np.sqrt(((np.arange(edep.shape[1], dtype=np.float32)[None, :] - center[:, None]) ** 2 * edep).sum(axis=1) / total)
    names: List[str] = []
    pieces = []
    for prefix, arr in [("log_edep", np.log1p(edep)), ("log_hits", np.log1p(hits)), ("present", present), ("cumfrac", cumfrac)]:
        pieces.append(arr)
        names.extend([f"{prefix}_layer_{i}" for i in range(arr.shape[1])])
    scalar_cols = ["n_positive_hits", "total_edep_mev", "front_deltae_mev", "residual_e_mev", "z_centroid_cm"]
    scalars = events[scalar_cols].to_numpy(dtype=float)
    scalars[:, 1:4] = np.log1p(np.maximum(scalars[:, 1:4], 0.0))
    scalars[:, 4] = np.nan_to_num(scalars[:, 4], nan=0.0) / 100.0
    pieces.extend([scalars, center[:, None], spread[:, None]])
    names.extend(scalar_cols + ["edep_centroid_layer", "edep_spread_layer"])
    return np.hstack(pieces).astype(np.float32), names


def choose_traditional_threshold(edep: np.ndarray, y_layer: np.ndarray, train: np.ndarray, grid: List[float]) -> Tuple[float, np.ndarray, pd.DataFrame]:
    rows = []
    best_threshold = float(grid[0])
    best_mae = float("inf")
    for threshold in grid:
        pred = deepest_visible_layer(edep, float(threshold))
        mae = float(mean_absolute_error(y_layer[train], pred[train]))
        acc = float(accuracy_score(y_layer[train], pred[train]))
        rows.append({"threshold_mev": float(threshold), "train_stop_mae_layers": mae, "train_exact_accuracy": acc})
        if mae < best_mae:
            best_mae = mae
            best_threshold = float(threshold)
    return best_threshold, deepest_visible_layer(edep, best_threshold), pd.DataFrame(rows)


def deepest_visible_layer(edep: np.ndarray, threshold: float) -> np.ndarray:
    visible = edep > threshold
    rev = visible[:, ::-1]
    deepest = edep.shape[1] - 1 - np.argmax(rev, axis=1)
    deepest[~visible.any(axis=1)] = 0
    return deepest.astype(np.float32)


def sample_train_indices(train: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    idx = np.flatnonzero(train)
    if len(idx) <= max_rows:
        return idx
    rng = np.random.default_rng(seed)
    return rng.choice(idx, size=max_rows, replace=False)


def fit_tabular_models(x: np.ndarray, y_residual: np.ndarray, train: np.ndarray, config: dict) -> Dict[str, object]:
    idx = sample_train_indices(train, int(config["max_tree_train_rows"]), int(config["random_seed"]) + 11)
    models: Dict[str, object] = {}
    models["ridge"] = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
    models["ridge"].fit(x[train], y_residual[train])
    models["gradient_boosted_trees"] = HistGradientBoostingRegressor(
        max_iter=180,
        learning_rate=0.045,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        random_state=int(config["random_seed"]) + 12,
    )
    models["gradient_boosted_trees"].fit(x[idx], y_residual[idx])
    return models


class TinyMLP(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 96),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(96, 48),
            nn.ReLU(),
            nn.Linear(48, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(1)


class WaveCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(5, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(32 + n_tab, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


class OrdinalStopCNN(nn.Module):
    def __init__(self, n_tab: int, n_thresholds: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(5, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(32 + n_tab, 80), nn.ReLU(), nn.Linear(80, n_thresholds))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1))


def torch_device():
    return torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu")


def fit_mlp(x: np.ndarray, y: np.ndarray, train: np.ndarray, config: dict) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train, int(config["max_torch_train_rows"]), int(config["random_seed"]) + 21)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ys = y[idx].astype(np.float32)
    ds = TensorDataset(torch.from_numpy(xs), torch.from_numpy(ys))
    loader = DataLoader(ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 22)
    device = torch_device()
    model = TinyMLP(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["torch_epochs"])):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_mlp(model: object, scaler: StandardScaler, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(xs), 16384):
        stop = min(start + 16384, len(xs))
        with torch.no_grad():
            out.append(model(torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy())
    return np.concatenate(out)


def fit_wave_cnn(wave: np.ndarray, x: np.ndarray, y: np.ndarray, train: np.ndarray, config: dict) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train, int(config["max_torch_train_rows"]), int(config["random_seed"]) + 31)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ws = wave[idx].astype(np.float32)
    ys = y[idx].astype(np.float32)
    ds = TensorDataset(torch.from_numpy(ws), torch.from_numpy(xs), torch.from_numpy(ys))
    loader = DataLoader(ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 32)
    device = torch_device()
    model = WaveCNN(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.2e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["torch_epochs"])):
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


def predict_wave_cnn(model: object, scaler: StandardScaler, wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(x), 16384):
        stop = min(start + 16384, len(x))
        with torch.no_grad():
            out.append(
                model(torch.from_numpy(wave[start:stop]).to(device), torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy()
            )
    return np.concatenate(out)


def fit_ordinal_cnn(wave: np.ndarray, x: np.ndarray, y_layer: np.ndarray, train: np.ndarray, config: dict) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train, int(config["max_torch_train_rows"]), int(config["random_seed"]) + 41)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ws = wave[idx].astype(np.float32)
    thresholds = np.arange(1, wave.shape[2], dtype=np.float32)
    ys = (y_layer[idx, None] >= thresholds[None, :]).astype(np.float32)
    ds = TensorDataset(torch.from_numpy(ws), torch.from_numpy(xs), torch.from_numpy(ys))
    loader = DataLoader(ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 42)
    device = torch_device()
    model = OrdinalStopCNN(x.shape[1], n_thresholds=wave.shape[2] - 1).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.0e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(config["torch_epochs"])):
        for wb, xb, yb in loader:
            wb = wb.to(device)
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            logits = model(wb, xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_ordinal_cnn(model: object, scaler: StandardScaler, wave: np.ndarray, x: np.ndarray, layer_max: int, spacing: float) -> Tuple[np.ndarray, np.ndarray]:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    layer_preds = []
    for start in range(0, len(x), 16384):
        stop = min(start + 16384, len(x))
        with torch.no_grad():
            logits = model(torch.from_numpy(wave[start:stop]).to(device), torch.from_numpy(xs[start:stop]).to(device))
            probs = torch.sigmoid(logits).cpu().numpy()
            layer_preds.append(probs.sum(axis=1))
    pred_layer = np.concatenate(layer_preds)
    pred_residual = (layer_max - pred_layer) * spacing
    return pred_residual, pred_layer


def layer_from_residual(pred_residual: np.ndarray, layer_max: int, spacing: float) -> np.ndarray:
    layer = layer_max - np.asarray(pred_residual, dtype=float) / spacing
    return np.clip(np.rint(layer), 0, layer_max).astype(int)


def res68_abs(error: np.ndarray) -> float:
    return float(np.percentile(np.abs(error), 68))


def run_block_bootstrap(events: pd.DataFrame, predictions: Dict[str, dict], held: np.ndarray, reps: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    held_idx = np.flatnonzero(held)
    blocks = [g.index.to_numpy(dtype=int) for _, g in events.loc[held].groupby("pseudo_run")]
    y_res = events["residual_range_cm"].to_numpy(dtype=float)
    y_layer = events["true_stop_layer"].to_numpy(dtype=int)
    rows = []
    for name, bundle in predictions.items():
        pred_res = bundle["residual_range_cm"]
        pred_layer = bundle["stop_layer"]
        held_err = pred_res[held_idx] - y_res[held_idx]
        row = {
            "method": name,
            "family": bundle["family"],
            "n_heldout": int(len(held_idx)),
            "residual_mae_cm": float(mean_absolute_error(y_res[held_idx], pred_res[held_idx])),
            "residual_bias_cm": float(np.median(held_err)),
            "residual_res68_cm": res68_abs(held_err),
            "stop_mae_layers": float(mean_absolute_error(y_layer[held_idx], pred_layer[held_idx])),
            "stop_exact_accuracy": float(accuracy_score(y_layer[held_idx], pred_layer[held_idx])),
        }
        draws = {key: [] for key in ["residual_mae_cm", "residual_bias_cm", "residual_res68_cm", "stop_mae_layers", "stop_exact_accuracy"]}
        for _ in range(reps):
            choice = rng.integers(0, len(blocks), size=len(blocks))
            idx = np.concatenate([blocks[i] for i in choice])
            err = pred_res[idx] - y_res[idx]
            draws["residual_mae_cm"].append(float(mean_absolute_error(y_res[idx], pred_res[idx])))
            draws["residual_bias_cm"].append(float(np.median(err)))
            draws["residual_res68_cm"].append(res68_abs(err))
            draws["stop_mae_layers"].append(float(mean_absolute_error(y_layer[idx], pred_layer[idx])))
            draws["stop_exact_accuracy"].append(float(accuracy_score(y_layer[idx], pred_layer[idx])))
        for key, vals in draws.items():
            lo, hi = np.percentile(np.asarray(vals, dtype=float), [2.5, 97.5])
            row[f"{key}_ci95"] = [float(lo), float(hi)]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("residual_mae_cm").reset_index(drop=True)


def by_run_rows(events: pd.DataFrame, predictions: Dict[str, dict], held: np.ndarray) -> pd.DataFrame:
    rows = []
    y_res = events["residual_range_cm"].to_numpy(dtype=float)
    y_layer = events["true_stop_layer"].to_numpy(dtype=int)
    for run, sub in events.loc[held].groupby("pseudo_run"):
        idx = sub.index.to_numpy(dtype=int)
        for name, bundle in predictions.items():
            err = bundle["residual_range_cm"][idx] - y_res[idx]
            rows.append(
                {
                    "pseudo_run": int(run),
                    "method": name,
                    "n": int(len(idx)),
                    "residual_mae_cm": float(mean_absolute_error(y_res[idx], bundle["residual_range_cm"][idx])),
                    "residual_bias_cm": float(np.median(err)),
                    "stop_exact_accuracy": float(accuracy_score(y_layer[idx], bundle["stop_layer"][idx])),
                }
            )
    return pd.DataFrame(rows)


def species_band_table(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for species, sub in events.groupby("dominant_sci_species"):
        if len(sub) < 20:
            continue
        for quantity in ["front_deltae_mev", "residual_e_mev", "total_edep_mev", "true_stop_layer"]:
            vals = sub[quantity].to_numpy(dtype=float)
            q16, q50, q84 = np.percentile(vals, [16, 50, 84])
            rows.append(
                {
                    "dominant_sci_species": species,
                    "quantity": quantity,
                    "n_events": int(len(sub)),
                    "q16": float(q16),
                    "median": float(q50),
                    "q84": float(q84),
                }
            )
    return pd.DataFrame(rows).sort_values(["dominant_sci_species", "quantity"]).reset_index(drop=True)


def make_deltae_plot(events: pd.DataFrame, out_path: Path, config: dict) -> None:
    rng = np.random.default_rng(int(config["random_seed"]) + 70)
    max_points = int(config["deltae_plot_max_points_per_species"])
    species_order = ["proton", "deuteron", "alpha", "electron", "gamma"]
    colors = {
        "proton": "#1f77b4",
        "deuteron": "#d62728",
        "alpha": "#2ca02c",
        "electron": "#9467bd",
        "gamma": "#ff7f0e",
    }
    fig, ax = plt.subplots(figsize=(8.0, 6.0), dpi=150)
    for species in species_order:
        sub = events[events["dominant_sci_species"] == species]
        if len(sub) == 0:
            continue
        if len(sub) > max_points:
            sub = sub.iloc[rng.choice(len(sub), size=max_points, replace=False)]
        ax.scatter(
            sub["residual_e_mev"],
            sub["front_deltae_mev"],
            s=4,
            alpha=0.22,
            linewidths=0,
            color=colors.get(species, "#555555"),
            label=f"{species} (n={len(events[events['dominant_sci_species'] == species]):,})",
        )
        full = events[events["dominant_sci_species"] == species]
        xb = np.percentile(full["residual_e_mev"], [16, 50, 84])
        yb = np.percentile(full["front_deltae_mev"], [16, 50, 84])
        ax.errorbar(
            xb[1],
            yb[1],
            xerr=[[xb[1] - xb[0]], [xb[2] - xb[1]]],
            yerr=[[yb[1] - yb[0]], [yb[2] - yb[1]]],
            fmt="o",
            markersize=5,
            color=colors.get(species, "#555555"),
            capsize=3,
        )
    ax.set_xlabel("Residual E after layer 0, MeV")
    ax.set_ylabel("Delta E in layer 0, MeV")
    ax.set_title("GEANT4 Sci_bar DeltaE-E truth bands")
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


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


def make_report(
    out_dir: Path,
    config: dict,
    result: dict,
    metrics: pd.DataFrame,
    byrun: pd.DataFrame,
    bands: pd.DataFrame,
    leakage: pd.DataFrame,
    threshold_scan: pd.DataFrame,
) -> None:
    winner = result["winner"]["method"]
    ci = result["winner"]["residual_mae_cm_ci95"]
    compact_metrics = metrics.copy()
    for col in [c for c in compact_metrics.columns if c.endswith("_ci95")]:
        compact_metrics[col] = compact_metrics[col].map(lambda v: f"[{v[0]:.4g}, {v[1]:.4g}]" if isinstance(v, list) else str(v))
    band_pivot = bands[bands["quantity"].isin(["front_deltae_mev", "residual_e_mev", "true_stop_layer"])].copy()
    lines = [
        "# S14h: Range and stopping-stave reconstruction from GEANT4 truth",
        "",
        "## Abstract",
        "",
        (
            f"This ticket uses the read-only GEANT4 ROOT truth file `{result['inputs']['geant4_root']}` "
            "to reconstruct the last Sci_bar layer with positive energy deposition and the corresponding residual range. "
            f"The raw ROOT reproduction gate reads {result['raw_reproduction']['tree_entries']:,} `hibeam` entries, "
            f"matching the expected {result['raw_reproduction']['expected_tree_entries']:,}, and finds "
            f"{result['raw_reproduction']['events_with_sci_bar']:,} entries with Sci_bar truth support. "
            f"The held-out pseudo-run winner is **{winner}** with residual-range MAE "
            f"{result['winner']['residual_mae_cm']:.4f} cm and block-bootstrap 95% CI [{ci[0]:.4f}, {ci[1]:.4f}] cm."
        ),
        "",
        "## Data, Scope, and Reproduction Gate",
        "",
        "The analysis reads the `hibeam` tree directly with `uproot`; no GEANT4 build or simulation rerun is performed. The 1M ROOT file is used because it exists on this worker; the 30k file is only a configured fallback. The simulation tree has no beam-run branch, so entries are partitioned into deterministic 50k-entry pseudo-runs. Held-out validation uses pseudo-runs 4, 9, 14, and 19, and all confidence intervals resample those held-out pseudo-runs as blocks.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| hibeam tree entries | {result['raw_reproduction']['expected_tree_entries']:,} | {result['raw_reproduction']['tree_entries']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        f"| events with positive Sci_bar EDep | n/a | {result['raw_reproduction']['events_with_sci_bar']:,} | n/a | true |",
        f"| positive Sci_bar hits | n/a | {result['raw_reproduction']['positive_sci_bar_hits']:,} | n/a | true |",
        "",
        "The supervised benchmark is conditional on a particle reaching Sci_bar. This is a scope restriction, not a detector-efficiency claim: events with no positive Sci_bar deposition do not have a stopping-stave label in this target definition.",
        "",
        "## Truth Target",
        "",
        "For event \\(e\\), the per-layer simulated amplitude vector is",
        "",
        "\\[ x_{e\\ell}=\\sum_{h\\in e,\\,L_h=\\ell} E_h, \\quad \\ell=0,\\ldots,7. \\]",
        "",
        "The truth stopping layer is the deepest Sci_bar layer with positive deposition,",
        "",
        "\\[ L_e^{\\star}=\\max\\{\\ell: x_{e\\ell}>0\\}. \\]",
        "",
        "With layer spacing \\(d=1\\,\\mathrm{cm}\\), the residual range to the back of the simulated Sci_bar stack is",
        "",
        "\\[ R_e^{\\star}=(7-L_e^{\\star})d. \\]",
        "",
        "A prediction \\(\\hat R_e\\) is converted back to a stopping-layer estimate by \\(\\hat L_e=\\mathrm{round}(7-\\hat R_e/d)\\), clipped to `[0,7]`.",
        "",
        "## Traditional and ML Methods",
        "",
        "The traditional method is a calibrated penetration-depth threshold: choose the deepest layer with \\(x_{e\\ell}>\\tau\\), where \\(\\tau\\) is selected on train pseudo-runs only by minimizing layer MAE. This is the appropriate non-neural baseline because it encodes the range-telescope rule directly while respecting a finite visible-energy threshold.",
        "",
        "The ML/NN panel contains ridge regression, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the five-channel layer sequence `(log EDep, log hit count, present flag, first time, z centroid)`, and a new ordinal cumulative CNN. The ordinal model predicts the seven ordered events \\(P(L^\\star\\ge k)\\) for \\(k=1,\\ldots,7\\); its expected layer is \\(\\sum_k P(L^\\star\\ge k)\\), making the architecture match the ordered range target rather than treating staves as unrelated classes.",
        "",
        "## Threshold Selection",
        "",
        md_table(threshold_scan, ["threshold_mev", "train_stop_mae_layers", "train_exact_accuracy"]),
        "",
        "## Metrics",
        "",
        "The primary ranking metric is held-out mean absolute error in residual range, \\(N^{-1}\\sum_e |\\hat R_e-R_e^\\star|\\). Secondary metrics are residual-range bias, residual-range res68, stop-layer MAE, and exact stop-layer accuracy. Bootstrap intervals resample held-out pseudo-runs with replacement, preserving event correlations inside each pseudo-run.",
        "",
        "## Head-to-Head Results",
        "",
        md_table(
            compact_metrics,
            [
                "method",
                "family",
                "n_heldout",
                "residual_mae_cm",
                "residual_mae_cm_ci95",
                "residual_res68_cm",
                "stop_mae_layers",
                "stop_exact_accuracy",
                "stop_exact_accuracy_ci95",
            ],
        ),
        "",
        "## Held-Out Pseudo-Run Stability",
        "",
        md_table(byrun[byrun["method"].isin([winner, "traditional_penetration_depth", "ridge", "gradient_boosted_trees"])], ["pseudo_run", "method", "n", "residual_mae_cm", "residual_bias_cm", "stop_exact_accuracy"]),
        "",
        "## DeltaE-E Truth Bands",
        "",
        "The telescope plot `deltae_e_truth_bands.png` uses layer 0 as \\(\\Delta E\\) and the sum of layers 1--7 as residual \\(E\\). Bands are grouped by the Sci_bar hit PDG carrying the largest event-level deposited energy. The plot is a visualization, while the table below records the central 16--84% bands for the full accepted sample.",
        "",
        "![DeltaE-E truth bands](deltae_e_truth_bands.png)",
        "",
        md_table(band_pivot, ["dominant_sci_species", "quantity", "n_events", "q16", "median", "q84"]),
        "",
        "## Leakage Controls",
        "",
        md_table(leakage, ["check", "value", "pass"]),
        "",
        "The deepest-positive definition is an intrinsic truth-label construction, so the study also records a forbidden ceiling sentinel in `leakage_checks.csv`: using `x>0` exactly recovers the label by construction and is not entered as a ranked method. Ranked methods either impose a train-calibrated visible threshold or learn from the same simulated amplitude vector that a detector-response model would expose.",
        "",
        "## Systematics and Caveats",
        "",
        "- The analysis is conditional on the current GEANT4 output and does not validate material composition, Birks quenching, optical transport, or ADC response against HRD data.",
        "- Pseudo-runs are deterministic entry blocks, not beam runs. They support block uncertainty estimates for this ROOT file but not time-dependent detector systematics.",
        "- The target is the last Sci_bar layer with any positive `EDep`; very small simulated depositions may be below real detector threshold. The traditional threshold scan quantifies sensitivity to that choice.",
        "- The DeltaE-E species label is the dominant deposited-energy PDG in Sci_bar, not a unique primary-particle assignment. Mixed secondary events are therefore summarized by dominant contribution.",
        "- Since the amplitude vector is itself the source of the stopping-label definition, absolute performance is best interpreted as an algorithmic closure on GEANT4 truth, not as a final detector-resolution claim.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14h_0000000011_1_rangestop.py --config configs/s14h_0000000011_1_rangestop.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14h_0000000011_1_rangestop.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    root_file = pick_root(config)

    print("1/7 aggregate GEANT4 truth from raw ROOT", flush=True)
    events, wave, counts = aggregate_events(config, root_file)
    expected = int(config["expected_tree_entries"]) if root_file == Path(config["geant4_root"]) else int(uproot.open(root_file)[config["tree"]].num_entries)
    if int(counts["tree_entries"]) != expected:
        raise RuntimeError(f"tree-entry reproduction failed: got {counts['tree_entries']}, expected {expected}")
    events = events.reset_index(drop=True)
    y_layer = events["true_stop_layer"].to_numpy(dtype=int)
    y_res = events["residual_range_cm"].to_numpy(dtype=float)
    edep = np.expm1(wave[:, 0, :])
    heldout_runs = set(int(x) for x in config["heldout_pseudo_runs"])
    held = events["pseudo_run"].isin(heldout_runs).to_numpy()
    train = ~held
    if int(held.sum()) == 0 or int(train.sum()) == 0:
        raise RuntimeError("empty train or held-out split")
    print(f"accepted={len(events)} train={int(train.sum())} heldout={int(held.sum())}", flush=True)

    print("2/7 feature construction and traditional threshold scan", flush=True)
    x, feature_names = tabular_features(events, wave)
    threshold, trad_layer, threshold_scan = choose_traditional_threshold(edep, y_layer, train, [float(v) for v in config["visible_threshold_grid_mev"]])
    layer_max = int(config["layer_max"])
    spacing = float(config["layer_spacing_cm"])
    predictions: Dict[str, dict] = {
        "traditional_penetration_depth": {
            "family": "traditional_threshold_range",
            "residual_range_cm": (layer_max - trad_layer) * spacing,
            "stop_layer": trad_layer.astype(int),
        }
    }

    print("3/7 ridge and gradient-boosted trees", flush=True)
    tab_models = fit_tabular_models(x, y_res, train, config)
    for name, model in tab_models.items():
        pred_res = np.clip(model.predict(x), 0.0, layer_max * spacing)
        predictions[name] = {
            "family": "ml_linear" if name == "ridge" else "ml_tree",
            "residual_range_cm": pred_res,
            "stop_layer": layer_from_residual(pred_res, layer_max, spacing),
        }

    print("4/7 tabular MLP", flush=True)
    torch_status = {"mlp": "not_run", "1d_cnn": "not_run", "ordinal_cumulative_cnn": "not_run"}
    try:
        mlp, mlp_scaler = fit_mlp(x, y_res, train, config)
        pred_res = np.clip(predict_mlp(mlp, mlp_scaler, x), 0.0, layer_max * spacing)
        predictions["mlp"] = {"family": "neural_tabular", "residual_range_cm": pred_res, "stop_layer": layer_from_residual(pred_res, layer_max, spacing)}
        torch_status["mlp"] = "trained"
    except Exception as exc:
        torch_status["mlp"] = f"failed: {exc}"

    print("5/7 1D-CNN", flush=True)
    try:
        cnn, cnn_scaler = fit_wave_cnn(wave, x, y_res, train, config)
        pred_res = np.clip(predict_wave_cnn(cnn, cnn_scaler, wave, x), 0.0, layer_max * spacing)
        predictions["1d_cnn"] = {"family": "neural_waveform", "residual_range_cm": pred_res, "stop_layer": layer_from_residual(pred_res, layer_max, spacing)}
        torch_status["1d_cnn"] = "trained"
    except Exception as exc:
        torch_status["1d_cnn"] = f"failed: {exc}"

    print("6/7 ordinal cumulative CNN", flush=True)
    try:
        ordinal, ordinal_scaler = fit_ordinal_cnn(wave, x, y_layer.astype(np.float32), train, config)
        pred_res, pred_layer_cont = predict_ordinal_cnn(ordinal, ordinal_scaler, wave, x, layer_max, spacing)
        predictions["ordinal_cumulative_cnn"] = {
            "family": "neural_ordinal_waveform",
            "residual_range_cm": np.clip(pred_res, 0.0, layer_max * spacing),
            "stop_layer": np.clip(np.rint(pred_layer_cont), 0, layer_max).astype(int),
        }
        torch_status["ordinal_cumulative_cnn"] = "trained"
    except Exception as exc:
        torch_status["ordinal_cumulative_cnn"] = f"failed: {exc}"

    print("7/7 metrics, plot, and report", flush=True)
    metrics = run_block_bootstrap(events, predictions, held, int(config["bootstrap_reps"]), int(config["random_seed"]) + 100)
    byrun = by_run_rows(events, predictions, held)
    bands = species_band_table(events)
    make_deltae_plot(events, out_dir / "deltae_e_truth_bands.png", config)

    forbidden = deepest_visible_layer(edep, 0.0)
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_tree_entry_reproduction_exact",
                "value": f"{counts['tree_entries']} of {expected}",
                "pass": int(counts["tree_entries"]) == int(expected),
            },
            {
                "check": "train_heldout_pseudo_run_overlap",
                "value": str(sorted(set(events.loc[train, "pseudo_run"]).intersection(set(events.loc[held, "pseudo_run"])))),
                "pass": set(events.loc[train, "pseudo_run"]).isdisjoint(set(events.loc[held, "pseudo_run"])),
            },
            {
                "check": "feature_names_exclude_truth_stop_and_pdg",
                "value": ",".join(feature_names),
                "pass": all("stop" not in name and "pdg" not in name and "species" not in name for name in feature_names),
            },
            {
                "check": "forbidden_deepest_positive_truth_sentinel_accuracy",
                "value": f"{accuracy_score(y_layer[held], forbidden[held]):.6f}",
                "pass": True,
            },
            {"check": "traditional_visible_threshold_mev", "value": f"{threshold:.6g}", "pass": True},
            {"check": "torch_mlp_status", "value": torch_status["mlp"], "pass": torch_status["mlp"] == "trained"},
            {"check": "torch_1d_cnn_status", "value": torch_status["1d_cnn"], "pass": torch_status["1d_cnn"] == "trained"},
            {
                "check": "torch_ordinal_cumulative_cnn_status",
                "value": torch_status["ordinal_cumulative_cnn"],
                "pass": torch_status["ordinal_cumulative_cnn"] == "trained",
            },
        ]
    )

    winner_row = metrics.iloc[0].to_dict()
    raw_repro = {
        "root_file": str(root_file),
        "tree": config["tree"],
        "expected_tree_entries": int(expected),
        "tree_entries": int(counts["tree_entries"]),
        "delta": int(counts["tree_entries"]) - int(expected),
        "pass": int(counts["tree_entries"]) == int(expected),
        "sci_bar_hits": int(counts["sci_bar_hits"]),
        "positive_sci_bar_hits": int(counts["positive_sci_bar_hits"]),
        "events_with_sci_bar": int(counts["events_with_sci_bar"]),
        "accepted_fraction": float(counts["accepted_fraction"]),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "inputs": {
            "geant4_root": str(root_file),
            "tree": config["tree"],
            "root_sha256": sha256_file(root_file),
            "root_bytes": int(root_file.stat().st_size),
        },
        "raw_reproduction": raw_repro,
        "split": {
            "split_kind": "deterministic pseudo-runs because GEANT4 tree has no run branch",
            "pseudo_run_size": int(config["pseudo_run_size"]),
            "train_pseudo_runs": sorted(int(x) for x in events.loc[train, "pseudo_run"].unique()),
            "heldout_pseudo_runs": sorted(int(x) for x in events.loc[held, "pseudo_run"].unique()),
            "n_train": int(train.sum()),
            "n_heldout": int(held.sum()),
        },
        "target": {
            "stop_layer_definition": "deepest Sci_bar_LayerID with Sci_bar_EDep > truth_min_edep_mev",
            "truth_min_edep_mev": float(config["truth_min_edep_mev"]),
            "layer_spacing_cm": spacing,
            "residual_range_cm": "(layer_max - true_stop_layer) * layer_spacing_cm",
        },
        "traditional": {
            "method": "traditional_penetration_depth",
            "visible_threshold_mev": float(threshold),
            "threshold_scan": json.loads(threshold_scan.to_json(orient="records")),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "residual_mae_cm": float(winner_row["residual_mae_cm"]),
            "residual_mae_cm_ci95": winner_row["residual_mae_cm_ci95"],
            "residual_res68_cm": float(winner_row["residual_res68_cm"]),
            "stop_mae_layers": float(winner_row["stop_mae_layers"]),
            "stop_exact_accuracy": float(winner_row["stop_exact_accuracy"]),
            "stop_exact_accuracy_ci95": winner_row["stop_exact_accuracy_ci95"],
        },
        "all_metrics": json.loads(metrics.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "next_tickets": [],
        "finding": (
            f"The best held-out residual-range method is {winner_row['method']} "
            f"({winner_row['family']}), with MAE={float(winner_row['residual_mae_cm']):.4f} cm "
            f"and stop-layer exact accuracy={float(winner_row['stop_exact_accuracy']):.4f}. "
            f"The calibrated traditional penetration-depth threshold is {threshold:.3g} MeV and remains the direct physics baseline. "
            "The forbidden deepest-positive sentinel is exact by construction and is reported only as a leakage ceiling, not as a ranked method."
        ),
        "runtime_sec": round(time.time() - t0, 1),
    }

    events.to_csv(out_dir / "event_summary.csv.gz", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    byrun.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    bands.to_csv(out_dir / "deltae_e_species_bands.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    threshold_scan.to_csv(out_dir / "traditional_threshold_scan.csv", index=False)
    pd.DataFrame([raw_repro]).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, metrics, byrun, bands, leakage, threshold_scan)

    outputs = [
        "REPORT.md",
        "result.json",
        "event_summary.csv.gz",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "deltae_e_species_bands.csv",
        "leakage_checks.csv",
        "traditional_threshold_scan.csv",
        "reproduction_match_table.csv",
        "deltae_e_truth_bands.png",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14h_0000000011_1_rangestop.py --config configs/s14h_0000000011_1_rangestop.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "awkward": getattr(ak, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "inputs": [result["inputs"]],
        "outputs": {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={result['winner']['method']}", flush=True)


if __name__ == "__main__":
    main()
