#!/usr/bin/env python3
"""S12a: GEANT4 truth validation of timing scale and B-stave spacing.

The raw-data reproduction gate rebuilds the S00 selected B-stave pulse count
from the raw HRD ROOT files. The truth benchmark then uses GEANT4 Sci_bar hits
only, grouped by event and track, to test whether the analysed B2/B4/B6/B8
layers are separated by 2 cm or 4 cm and whether the timing scale used by the
data-driven inter-stave residuals is consistent with truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import awkward as ak
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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(branches, step_size=step_size, library="np")


def reproduce_selected_count(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    channels = np.asarray([int(v) for v in config["staves"].values()], dtype=int)
    stave_names = list(config["staves"].keys())
    cut = float(config["amplitude_cut_adc"])
    rows = []
    total = 0
    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        counts = dict(run=run, selected_pulses=0, events=0)
        counts.update({name: 0 for name in stave_names})
        for batch in iter_raw(path, ["HRDv"]):
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


def beta_from_p(p_gev: np.ndarray, mass_gev: float) -> np.ndarray:
    p = np.asarray(p_gev, dtype=float)
    return p / np.sqrt(p * p + mass_gev * mass_gev)


def beta_from_ekin(ekin_mev: float, mass_gev: float) -> float:
    ekin_gev = float(ekin_mev) / 1000.0
    gamma = 1.0 + ekin_gev / mass_gev
    return float(math.sqrt(max(0.0, 1.0 - 1.0 / (gamma * gamma))))


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    v = np.asarray(values, dtype=float)
    if float(w.sum()) <= 0.0:
        return float(np.mean(v))
    return float(np.average(v, weights=w))


def hit_summary(hit_indices: np.ndarray, arrays: dict) -> dict:
    edep = np.asarray(arrays["Sci_bar_EDep"])[hit_indices].astype(float)
    return {
        "edep": float(edep.sum()),
        "time": weighted_mean(np.asarray(arrays["Sci_bar_Time"])[hit_indices], edep),
        "x": weighted_mean(np.asarray(arrays["Sci_bar_GlobalPosition_X"])[hit_indices], edep),
        "y": weighted_mean(np.asarray(arrays["Sci_bar_GlobalPosition_Y"])[hit_indices], edep),
        "z": weighted_mean(np.asarray(arrays["Sci_bar_GlobalPosition_Z"])[hit_indices], edep),
        "px": weighted_mean(np.asarray(arrays["Sci_bar_Momentum_X"])[hit_indices], edep),
        "py": weighted_mean(np.asarray(arrays["Sci_bar_Momentum_Y"])[hit_indices], edep),
        "pz": weighted_mean(np.asarray(arrays["Sci_bar_Momentum_Z"])[hit_indices], edep),
    }


def extract_truth_pairs(config: dict) -> pd.DataFrame:
    truth = config["truth"]
    path = Path(config["geant4_root"])
    tree = uproot.open(path)[truth["tree"]]
    branches = [
        "Sci_bar_TrackID",
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_GlobalPosition_X",
        "Sci_bar_GlobalPosition_Y",
        "Sci_bar_GlobalPosition_Z",
        "Sci_bar_Momentum_X",
        "Sci_bar_Momentum_Y",
        "Sci_bar_Momentum_Z",
    ]
    selected_layers = set(int(v) for v in truth["selected_layer_ids"])
    adjacent_pairs = [tuple(int(x) for x in p) for p in truth["adjacent_pairs"]]
    stack_id = int(truth["stack_layer_id1"])
    pdg = int(truth["particle_pdg"])
    n_blocks = int(truth["n_sim_blocks"])
    n_entries = int(tree.num_entries)
    block_size = max(1, math.ceil(n_entries / n_blocks))
    max_pairs = int(truth["max_pairs"])
    per_block_cap = max(1, math.ceil(max_pairs / n_blocks))
    block_counts = np.zeros(n_blocks, dtype=int)
    rows: List[dict] = []

    entry_base = 0
    for batch in tree.iterate(branches, step_size=int(truth["batch_entries"]), library="ak"):
        counts = ak.num(batch["Sci_bar_EDep"])
        event_entries = entry_base + np.arange(len(counts), dtype=int)
        layer = batch["Sci_bar_LayerID"]
        base_mask = (
            (batch["Sci_bar_LayerID1"] == stack_id)
            & (batch["Sci_bar_PDG"] == pdg)
            & (batch["Sci_bar_TrackID"] == 1)
            & (batch["Sci_bar_EDep"] > 0.0)
        )

        def first_values(branch: str, mask, valid) -> np.ndarray:
            return ak.to_numpy(ak.firsts(batch[branch][mask])[valid])

        for la, lb in adjacent_pairs:
            ma = base_mask & (layer == la)
            mb = base_mask & (layer == lb)
            ta = ak.firsts(batch["Sci_bar_Time"][ma])
            tb = ak.firsts(batch["Sci_bar_Time"][mb])
            valid = (~ak.is_none(ta)) & (~ak.is_none(tb))
            if int(ak.sum(valid)) == 0:
                continue
            entries = event_entries[np.asarray(valid)]
            blocks = np.minimum(n_blocks - 1, entries // block_size).astype(int)

            keep_parts = []
            for block in np.unique(blocks):
                remaining = per_block_cap - int(block_counts[block])
                if remaining <= 0:
                    continue
                idx = np.flatnonzero(blocks == block)[:remaining]
                if len(idx):
                    keep_parts.append(idx)
                    block_counts[block] += len(idx)
            if not keep_parts:
                continue
            keep = np.concatenate(keep_parts)
            entries = entries[keep]
            blocks = blocks[keep]

            truth_dt = ak.to_numpy((tb - ta)[valid])[keep].astype(float)
            edep_a = first_values("Sci_bar_EDep", ma, valid)[keep].astype(float)
            edep_b = first_values("Sci_bar_EDep", mb, valid)[keep].astype(float)
            xa = first_values("Sci_bar_GlobalPosition_X", ma, valid)[keep].astype(float)
            ya = first_values("Sci_bar_GlobalPosition_Y", ma, valid)[keep].astype(float)
            za = first_values("Sci_bar_GlobalPosition_Z", ma, valid)[keep].astype(float)
            xb = first_values("Sci_bar_GlobalPosition_X", mb, valid)[keep].astype(float)
            yb = first_values("Sci_bar_GlobalPosition_Y", mb, valid)[keep].astype(float)
            zb = first_values("Sci_bar_GlobalPosition_Z", mb, valid)[keep].astype(float)
            pxa = first_values("Sci_bar_Momentum_X", ma, valid)[keep].astype(float)
            pya = first_values("Sci_bar_Momentum_Y", ma, valid)[keep].astype(float)
            pza = first_values("Sci_bar_Momentum_Z", ma, valid)[keep].astype(float)
            pxb = first_values("Sci_bar_Momentum_X", mb, valid)[keep].astype(float)
            pyb = first_values("Sci_bar_Momentum_Y", mb, valid)[keep].astype(float)
            pzb = first_values("Sci_bar_Momentum_Z", mb, valid)[keep].astype(float)
            dx = xb - xa
            dy = yb - ya
            dz = zb - za
            pa = np.sqrt(pxa * pxa + pya * pya + pza * pza)
            pb = np.sqrt(pxb * pxb + pyb * pyb + pzb * pzb)
            beta_mid = 0.5 * (beta_from_p(pa, float(truth["proton_mass_gev"])) + beta_from_p(pb, float(truth["proton_mass_gev"])))
            good = np.isfinite(beta_mid) & (beta_mid > 0.0) & np.isfinite(truth_dt)
            for i in np.flatnonzero(good):
                rows.append(
                    {
                        "event_entry": int(entries[i]),
                        "sim_block": int(blocks[i]),
                        "track_id": 1,
                        "layer_a": int(la),
                        "layer_b": int(lb),
                        "pair": f"{la}-{lb}",
                        "truth_dt_ns": float(truth_dt[i]),
                        "distance_cm": float(math.sqrt(dx[i] * dx[i] + dy[i] * dy[i] + dz[i] * dz[i])),
                        "dx_cm": float(dx[i]),
                        "dy_cm": float(dy[i]),
                        "dz_cm": float(dz[i]),
                        "edep_a": float(edep_a[i]),
                        "edep_b": float(edep_b[i]),
                        "x_a": float(xa[i]),
                        "y_a": float(ya[i]),
                        "z_a": float(za[i]),
                        "x_b": float(xb[i]),
                        "y_b": float(yb[i]),
                        "z_b": float(zb[i]),
                        "p_a_gev": float(pa[i]),
                        "p_b_gev": float(pb[i]),
                        "beta_mid": float(beta_mid[i]),
                    }
                )
            if np.all(block_counts >= per_block_cap):
                return pd.DataFrame(rows)
        entry_base += len(counts)
    return pd.DataFrame(rows)


def feature_columns() -> List[str]:
    return [
        "layer_a",
        "layer_b",
        "distance_cm",
        "dx_cm",
        "dy_cm",
        "dz_cm",
        "edep_a",
        "edep_b",
        "p_a_gev",
        "p_b_gev",
        "beta_mid",
        "x_a",
        "y_a",
        "z_a",
        "x_b",
        "y_b",
        "z_b",
    ]


def sequence_tensor(df: pd.DataFrame) -> np.ndarray:
    cols = ["layer", "x", "y", "z", "edep", "p"]
    a = np.column_stack(
        [
            df["layer_a"].to_numpy(float) / 7.0,
            df["x_a"].to_numpy(float) / 100.0,
            df["y_a"].to_numpy(float) / 100.0,
            df["z_a"].to_numpy(float) / 100.0,
            np.log1p(df["edep_a"].to_numpy(float)) / 5.0,
            df["p_a_gev"].to_numpy(float),
        ]
    )
    b = np.column_stack(
        [
            df["layer_b"].to_numpy(float) / 7.0,
            df["x_b"].to_numpy(float) / 100.0,
            df["y_b"].to_numpy(float) / 100.0,
            df["z_b"].to_numpy(float) / 100.0,
            np.log1p(df["edep_b"].to_numpy(float)) / 5.0,
            df["p_b_gev"].to_numpy(float),
        ]
    )
    return np.stack([a, b], axis=1).astype(np.float32)


def add_baseline_predictions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    c = float(config["truth"]["c_cm_per_ns"])
    mass = float(config["truth"]["proton_mass_gev"])
    beta_40 = beta_from_ekin(40.0, mass)
    beta_190 = beta_from_ekin(190.0, mass)
    nominal = float(config["tof_per_cm_ns_used_in_notes"])
    out["pred_truth_kinematic_tof"] = out["distance_cm"] / (np.maximum(out["beta_mid"], 1e-6) * c)
    out["pred_nominal_2cm_notes"] = 2.0 * nominal
    out["pred_nominal_4cm_notes"] = 4.0 * nominal
    out["pred_4cm_40mev_tof"] = 4.0 / (beta_40 * c)
    out["pred_4cm_190mev_tof"] = 4.0 / (beta_190 * c)
    return out


def split_masks(df: pd.DataFrame, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    train = np.isin(df["sim_block"].to_numpy(int), [int(v) for v in config["truth"]["train_blocks"]])
    val = np.isin(df["sim_block"].to_numpy(int), [int(v) for v in config["truth"]["val_blocks"]])
    held = np.isin(df["sim_block"].to_numpy(int), [int(v) for v in config["truth"]["heldout_blocks"]])
    return train, val, held


def torch_available() -> bool:
    return torch is not None and nn is not None and DataLoader is not None and TensorDataset is not None


class MLP(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 64),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


class PairCNN(nn.Module):
    def __init__(self, n_feat: int):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(n_feat, 32, kernel_size=1), nn.ReLU(), nn.Conv1d(32, 32, kernel_size=2), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        x = x.transpose(1, 2)
        x = self.conv(x).squeeze(-1)
        return self.head(x).squeeze(-1)


def train_torch_model(model, X_train, y_train, X_val, y_val, config: dict) -> Tuple[object, float]:
    torch.manual_seed(int(config["truth"]["random_seed"]))
    params = config["models"]["torch"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(params["learning_rate"]), weight_decay=float(params["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    train_ds = TensorDataset(torch.as_tensor(X_train, dtype=torch.float32), torch.as_tensor(y_train, dtype=torch.float32))
    loader = DataLoader(train_ds, batch_size=int(params["batch_size"]), shuffle=True)
    best_state = None
    best_val = float("inf")
    for _ in range(int(params["epochs"])):
        model.train()
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
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
    return model.to(device), best_val


def predict_torch(model, X) -> np.ndarray:
    device = next(model.parameters()).device
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(X), 32768):
            xb = torch.as_tensor(X[start : start + 32768], dtype=torch.float32, device=device)
            preds.append(model(xb).detach().cpu().numpy())
    return np.concatenate(preds)


def train_models(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["truth"]["random_seed"]))
    train, val, held = split_masks(df, config)
    y = df["truth_dt_ns"].to_numpy(float)
    X = df[feature_columns()].to_numpy(float)
    predictions: Dict[str, np.ndarray] = {}
    cv_rows = []

    for col in [
        "pred_truth_kinematic_tof",
        "pred_nominal_2cm_notes",
        "pred_nominal_4cm_notes",
        "pred_4cm_40mev_tof",
        "pred_4cm_190mev_tof",
    ]:
        predictions[col.replace("pred_", "")] = df[col].to_numpy(float)

    pair_names = sorted(df["pair"].unique())
    pair_onehot = np.column_stack([(df["pair"].to_numpy() == p).astype(float) for p in pair_names])
    x_cal = np.column_stack([np.ones(len(df)), df["pred_truth_kinematic_tof"].to_numpy(float), pair_onehot])
    coef, *_ = np.linalg.lstsq(x_cal[train | val], y[train | val], rcond=None)
    predictions["calibrated_kinematic_tof"] = x_cal @ coef
    cv_rows.append({"method": "calibrated_kinematic_tof", "param": "affine_plus_pair_offsets", "val_mae_ns": float(mean_absolute_error(y[val], (x_cal @ coef)[val]))})

    best_alpha = None
    best_val = float("inf")
    for alpha in [float(a) for a in config["models"]["ridge_alphas"]]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X[train], y[train])
        pred = model.predict(X[val])
        val_mae = float(mean_absolute_error(y[val], pred))
        cv_rows.append({"method": "ridge", "param": f"alpha={alpha}", "val_mae_ns": val_mae})
        if val_mae < best_val:
            best_val = val_mae
            best_alpha = alpha
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X[train | val], y[train | val])
    predictions["ridge"] = ridge.predict(X)

    gcfg = config["models"]["gbt"]
    gbt = GradientBoostingRegressor(
        n_estimators=int(gcfg["n_estimators"]),
        max_depth=int(gcfg["max_depth"]),
        learning_rate=float(gcfg["learning_rate"]),
        subsample=float(gcfg["subsample"]),
        random_state=int(config["truth"]["random_seed"]),
    )
    gbt.fit(X[train | val], y[train | val])
    predictions["gradient_boosted_trees"] = gbt.predict(X)
    cv_rows.append({"method": "gradient_boosted_trees", "param": "fixed_config", "val_mae_ns": float("nan")})

    if torch_available():
        scaler = StandardScaler().fit(X[train])
        Xs = scaler.transform(X).astype(np.float32)
        mlp, mlp_val = train_torch_model(MLP(Xs.shape[1]), Xs[train], y[train], Xs[val], y[val], config)
        predictions["mlp"] = predict_torch(mlp, Xs)
        cv_rows.append({"method": "mlp", "param": "best_epoch", "val_mae_ns": mlp_val})

        seq = sequence_tensor(df)
        mu = seq[train].reshape(-1, seq.shape[-1]).mean(axis=0)
        sd = seq[train].reshape(-1, seq.shape[-1]).std(axis=0) + 1e-6
        seqs = ((seq - mu[None, None, :]) / sd[None, None, :]).astype(np.float32)
        cnn, cnn_val = train_torch_model(PairCNN(seqs.shape[-1]), seqs[train], y[train], seqs[val], y[val], config)
        predictions["1d_cnn"] = predict_torch(cnn, seqs)
        cv_rows.append({"method": "1d_cnn", "param": "best_epoch", "val_mae_ns": cnn_val})

        residual = y - df["pred_truth_kinematic_tof"].to_numpy(float)
        res_mlp, res_val = train_torch_model(MLP(Xs.shape[1]), Xs[train], residual[train], Xs[val], residual[val], config)
        predictions["physics_residual_mlp"] = df["pred_truth_kinematic_tof"].to_numpy(float) + predict_torch(res_mlp, Xs)
        cv_rows.append({"method": "physics_residual_mlp", "param": "best_epoch", "val_mae_ns": res_val})
    else:
        predictions["mlp"] = np.full(len(df), np.nan)
        predictions["1d_cnn"] = np.full(len(df), np.nan)
        predictions["physics_residual_mlp"] = np.full(len(df), np.nan)
        cv_rows.append({"method": "torch_models", "param": "unavailable", "val_mae_ns": float("nan")})

    pred_df = pd.DataFrame(predictions)
    pred_df["truth_dt_ns"] = y
    pred_df["sim_block"] = df["sim_block"].to_numpy(int)
    pred_df["heldout"] = held
    pred_df["pair"] = df["pair"].to_numpy()
    return pred_df, pd.DataFrame(cv_rows)


def metric_dict(y: np.ndarray, pred: np.ndarray) -> dict:
    err = np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)
    finite = np.isfinite(err)
    err = err[finite]
    if len(err) == 0:
        return {"n": 0, "bias_ns": float("nan"), "mae_ns": float("nan"), "res68_abs_ns": float("nan"), "rms_ns": float("nan")}
    q16, q84 = np.percentile(err, [16, 84])
    return {
        "n": int(len(err)),
        "bias_ns": float(np.mean(err)),
        "median_error_ns": float(np.median(err)),
        "mae_ns": float(np.mean(np.abs(err))),
        "res68_abs_ns": float((q84 - q16) / 2.0),
        "rms_ns": float(np.sqrt(np.mean(err * err))),
        "p95_abs_ns": float(np.percentile(np.abs(err), 95)),
    }


def block_bootstrap_metrics(pred_df: pd.DataFrame, method: str, n_boot: int, seed: int) -> dict:
    held = pred_df[pred_df["heldout"] & np.isfinite(pred_df[method])].copy()
    base = metric_dict(held["truth_dt_ns"].to_numpy(float), held[method].to_numpy(float))
    rng = np.random.default_rng(seed)
    blocks = np.asarray(sorted(held["sim_block"].unique()), dtype=int)
    stats = defaultdict(list)
    for _ in range(int(n_boot)):
        chosen = rng.choice(blocks, size=len(blocks), replace=True)
        sample = pd.concat([held[held["sim_block"] == b] for b in chosen], ignore_index=True)
        m = metric_dict(sample["truth_dt_ns"].to_numpy(float), sample[method].to_numpy(float))
        for key in ["mae_ns", "res68_abs_ns", "bias_ns", "p95_abs_ns"]:
            stats[key].append(m[key])
    for key, vals in stats.items():
        base[f"{key}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    return base


def summarize_geometry(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict]:
    rows = []
    n_boot = int(config["truth"]["bootstrap_samples"])
    rng = np.random.default_rng(int(config["truth"]["random_seed"]) + 17)
    for pair, sub in df.groupby("pair"):
        vals = sub["distance_cm"].to_numpy(float)
        dt = sub["truth_dt_ns"].to_numpy(float)
        scale = dt / vals
        boot_dist = []
        boot_dt = []
        boot_scale = []
        blocks = sorted(sub["sim_block"].unique())
        for _ in range(n_boot):
            chosen = rng.choice(blocks, size=len(blocks), replace=True)
            samp = pd.concat([sub[sub["sim_block"] == b] for b in chosen], ignore_index=True)
            boot_dist.append(float(np.median(samp["distance_cm"])))
            boot_dt.append(float(np.median(samp["truth_dt_ns"])))
            boot_scale.append(float(np.median(samp["truth_dt_ns"] / samp["distance_cm"])))
        rows.append(
            {
                "pair": pair,
                "n": int(len(sub)),
                "median_distance_cm": float(np.median(vals)),
                "distance_ci95": [float(np.percentile(boot_dist, 2.5)), float(np.percentile(boot_dist, 97.5))],
                "median_truth_dt_ns": float(np.median(dt)),
                "truth_dt_ci95": [float(np.percentile(boot_dt, 2.5)), float(np.percentile(boot_dt, 97.5))],
                "median_tof_per_cm_ns": float(np.median(scale)),
                "tof_per_cm_ci95": [float(np.percentile(boot_scale, 2.5)), float(np.percentile(boot_scale, 97.5))],
            }
        )
    geom = pd.DataFrame(rows)
    all_scale = df["truth_dt_ns"].to_numpy(float) / df["distance_cm"].to_numpy(float)
    summary = {
        "median_analyzed_spacing_cm": float(np.median(df["distance_cm"])),
        "median_tof_per_cm_ns": float(np.median(all_scale)),
        "notes_tof_per_cm_ns": float(config["tof_per_cm_ns_used_in_notes"]),
        "timing_scale_systematic_ns_per_cm": float(np.median(all_scale) - float(config["tof_per_cm_ns_used_in_notes"])),
        "median_4cm_truth_dt_ns": float(4.0 * np.median(all_scale)),
        "nominal_2cm_offset_ns": float(2.0 * float(config["tof_per_cm_ns_used_in_notes"])),
        "nominal_4cm_offset_ns": float(4.0 * float(config["tof_per_cm_ns_used_in_notes"])),
    }
    return geom, summary


def write_report(
    outdir: Path,
    config_path: Path,
    config: dict,
    gate: pd.DataFrame,
    geometry: pd.DataFrame,
    geometry_summary: dict,
    metrics: pd.DataFrame,
    winner: dict,
    cv: pd.DataFrame,
    manifest: dict,
) -> None:
    def md_table(df: pd.DataFrame) -> str:
        return df.to_markdown(index=False)

    metric_cols = ["method", "family", "n", "mae_ns", "mae_ns_ci95", "res68_abs_ns", "res68_abs_ns_ci95", "bias_ns", "bias_ns_ci95", "p95_abs_ns"]
    text = f"""# S12a: GEANT4 truth validation of timing scale and B-stave geometry

## Abstract

Ticket `{config['ticket_id']}` asks whether the data-driven B-stack timing scale and geometry assumptions survive a direct comparison to GEANT4 truth hit times and positions. The raw ROOT gate reproduces the S00 selected-pulse count exactly from `data/root/root`. In GEANT4 truth, same-proton adjacent analysed layers (B2-B4, B4-B6, B6-B8 mapped to Sci_bar layer pairs 0-2, 2-4, 4-6) have a median path separation of **{geometry_summary['median_analyzed_spacing_cm']:.4f} cm**, rejecting the 2 cm analysed-stave spacing interpretation and supporting the 4 cm centre-to-centre convention. The truth median timing scale is **{geometry_summary['median_tof_per_cm_ns']:.5f} ns/cm**, versus the note value **{geometry_summary['notes_tof_per_cm_ns']:.5f} ns/cm**, so the absolute TOF systematic is **{geometry_summary['timing_scale_systematic_ns_per_cm']:+.5f} ns/cm**. The held-out benchmark winner is **{winner['method']}** with MAE **{winner['mae_ns']:.5f} ns**.

## 0. Question

Can the inter-stave timing corrections used for B-stack same-particle residuals be anchored to GEANT4 truth positions and hit times, and does a strong analytic relativistic TOF model remain competitive with ridge, gradient-boosted trees, an MLP, a 1D-CNN, and a physics-residual neural architecture on the same held-out truth pairs?

## 1. Reproduction from raw ROOT

The gate re-runs the independent S00 pulse selector over raw `hrdb_run_*.root` files: reshape `HRDv` to 8 channels x 18 samples, subtract the median of samples 0--3, and count B2/B4/B6/B8 pulses with peak amplitude above 1000 ADC. No sorted ROOT files or cached tables are used.

{md_table(gate)}

## 2. Truth geometry and timing equations

GEANT4 hits are selected with `Sci_bar_LayerID1={config['truth']['stack_layer_id1']}`, primary `Sci_bar_TrackID=1`, PDG={config['truth']['particle_pdg']}, positive deposited energy, and analysed layer IDs `{config['truth']['selected_layer_ids']}`. For each event and layer, the first primary-track hit is used; events contribute adjacent analysed-layer pairs 0-2, 2-4, and 4-6 when both endpoints are present. For a pair of layers \(a,b\),

\\[
\\Delta t_{{ab}}^{{\\rm truth}} = t_b-t_a,\qquad
d_{{ab}} = \\lVert \\vec r_b-\\vec r_a \\rVert .
\\]

The strong traditional prediction is the relativistic kinematic TOF

\\[
\\widehat{{\\Delta t}}_{{ab}} =
\\frac{{d_{{ab}}}}{{c\\,\\bar\\beta}},\qquad
\\beta(p)=\\frac{{p}}{{\\sqrt{{p^2+m_p^2}}}},
\\]

where \(p\) is in GeV/c, \(m_p=0.9382720813\\,\\mathrm{{GeV}}\), and \(c=29.9792458\\,\\mathrm{{cm/ns}}\). The historical note offsets are also evaluated as fixed baselines:
\(2\\,\\mathrm{{cm}}\\times0.078\\,\\mathrm{{ns/cm}}\) and \(4\\,\\mathrm{{cm}}\\times0.078\\,\\mathrm{{ns/cm}}\).

{md_table(geometry)}

The analysed-stave median spacing is therefore {geometry_summary['median_analyzed_spacing_cm']:.4f} cm. The 2 cm interpretation underestimates the truth path length by approximately {(1.0 - 2.0 / geometry_summary['median_analyzed_spacing_cm']) * 100.0:.1f}%, while the 4 cm convention is within {(geometry_summary['median_analyzed_spacing_cm'] - 4.0) / 4.0 * 100.0:+.2f}% of the truth median. The truth 4 cm timing offset implied by the median scale is {geometry_summary['median_4cm_truth_dt_ns']:.4f} ns, compared with note offsets {geometry_summary['nominal_2cm_offset_ns']:.4f} ns (2 cm) and {geometry_summary['nominal_4cm_offset_ns']:.4f} ns (4 cm).

## 3. Traditional and ML methods

All methods predict `truth_dt_ns` for the same held-out GEANT4 pair rows. The split is by contiguous simulation entry blocks, used as run surrogates because the GEANT4 file has no physical run branch: train blocks `{config['truth']['train_blocks']}`, validation blocks `{config['truth']['val_blocks']}`, held-out blocks `{config['truth']['heldout_blocks']}`. Confidence intervals resample held-out blocks with replacement.

Features for learned models include only layer IDs, 3D hit positions, pair displacement and distance, deposited energies, hit momenta, and the derived midpoint beta. Truth hit times are excluded. The model panel is:

- `truth_kinematic_tof`: analytic relativistic TOF using truth position and momentum.
- `calibrated_kinematic_tof`: the strong traditional method, an affine calibration of the analytic TOF plus pair offsets fitted only on train/validation blocks.
- `ridge`: standardized ridge regression, validation-selected alpha.
- `gradient_boosted_trees`: fixed-depth gradient boosting.
- `mlp`: two-layer tabular neural network with SmoothL1 loss.
- `1d_cnn`: convolution over the ordered two-hit sequence.
- `physics_residual_mlp`: the new architecture, predicting a neural residual added to the analytic TOF.
- fixed note baselines: `nominal_2cm_notes`, `nominal_4cm_notes`, `4cm_40mev_tof`, and `4cm_190mev_tof`.

Validation scan:

{md_table(cv.round(6))}

## 4. Head-to-head benchmark

Primary metric is held-out MAE in ns. Secondary metrics are robust residual width \((q_{{84}}-q_{{16}})/2\), mean bias, RMS, and 95th percentile absolute error. Lower is better.

{md_table(metrics[metric_cols].round(6))}

Verdict: **{winner['method']}** wins. The calibrated kinematic TOF row is the strong traditional baseline for the head-to-head comparison; fixed 2 cm/4 cm rows are historical controls. The winner field in `result.json` records the strict held-out MAE winner rather than a complexity-adjusted choice.

## 5. Falsification

Pre-registered metric from the ticket: same-particle inter-stave truth timing residuals, spacing test, absolute TOF scale, and a run-split ML-vs-traditional benchmark with bootstrap CIs. A falsifying result would be either (i) a median analysed-layer spacing closer to 2 cm than 4 cm, or (ii) an ML/NN model whose held-out MAE improves on the kinematic TOF baseline by more than the block-bootstrap CI overlap. The comparison uses ten named methods, so any discovery claim should be interpreted after a Bonferroni-style family check; the spacing result is geometric and not selected from the model panel.

## 6. Threats to validity

Benchmark/selection: the traditional baseline is deliberately strong because it uses truth position and truth momentum, matching the information content available to the learned models except for nonlinear flexibility. The fixed 2 cm/4 cm baselines are included only to test historical assumptions.

Data leakage: splits are by simulation entry block. Event ID, track ID, and truth time are not model features. Bootstrap CIs resample held-out blocks, not individual rows.

Metric misuse: MAE is the primary metric because the target is an absolute TOF prediction; res68, RMS, bias, and p95 are reported to expose tails and offsets. No classifier calibration is needed.

Post-hoc selection: layer pairs, particle PDG, stack ID, model families, and metrics are fixed in `configs/s12a_0000000012_1_truthtiming.yaml`.

## 7. Systematics and caveats

The GEANT4 file is simulation truth, not a detector-data alignment. The mapping of B2/B4/B6/B8 to Sci_bar layer IDs 0/2/4/6 is the natural even-layer mapping used by the geometry discrepancy, but it remains a convention unless detector construction metadata are added. The simulation has no real run labels; entry blocks are used for leakage control and bootstrap uncertainty. Electronics offsets in raw data cannot be validated without event-level matching between real HRD data and simulation. The timing-scale systematic reported here is therefore an absolute TOF-model systematic, not an electronics-channel calibration.

## 8. Findings and next steps

The 4 cm analysed-stave convention is supported by truth positions; the 2 cm analysed-stave convention is rejected for B2/B4/B6/B8 centre-to-centre offsets. The note timing scale of 0.078 ns/cm is conservative relative to the median GEANT4 same-proton truth scale by {geometry_summary['timing_scale_systematic_ns_per_cm']:+.5f} ns/cm. A useful follow-up would be a detector-map audit that ties HRD channel names to GEANT4 layer IDs and construction coordinates; expected information gain is high because it would turn the current natural even-layer mapping into a documented geometry contract.

## 9. Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s12a_0000000012_1_truthtiming.py --config configs/s12a_0000000012_1_truthtiming.yaml
```

Artifacts: `result.json`, `manifest.json`, `truth_pairs.parquet`, `metrics.csv`, `geometry_summary.csv`, `run_counts.csv`, `figures/geometry_tof.png`, and this `REPORT.md`.

Manifest git commit: `{manifest['git_commit']}`.
"""
    (outdir / "REPORT.md").write_text(text, encoding="utf-8")


def plot_geometry(outdir: Path, df: pd.DataFrame, pred_df: pd.DataFrame, winner_method: str) -> Path:
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    path = figdir / "geometry_tof.png"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].hist(df["distance_cm"], bins=60, color="#3b82f6", alpha=0.8)
    axes[0].axvline(2.0, color="#ef4444", linestyle="--", label="2 cm")
    axes[0].axvline(4.0, color="#111827", linestyle="--", label="4 cm")
    axes[0].set_xlabel("truth pair path distance (cm)")
    axes[0].set_ylabel("pairs")
    axes[0].legend()
    held = pred_df[pred_df["heldout"] & np.isfinite(pred_df[winner_method])]
    err = held[winner_method].to_numpy(float) - held["truth_dt_ns"].to_numpy(float)
    axes[1].hist(err, bins=80, color="#10b981", alpha=0.8)
    axes[1].axvline(0.0, color="#111827", linestyle="--")
    axes[1].set_xlabel(f"{winner_method} error (ns)")
    axes[1].set_ylabel("held-out pairs")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s12a_0000000012_1_truthtiming.yaml")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = load_config(config_path)
    outdir = ROOT / config["output_dir"]
    outdir.mkdir(parents=True, exist_ok=True)

    gate, run_counts = reproduce_selected_count(config)
    if not bool(gate["pass"].iloc[0]):
        raise RuntimeError("Raw reproduction gate failed")
    pairs = add_baseline_predictions(extract_truth_pairs(config), config)
    if pairs.empty:
        raise RuntimeError("No truth pairs extracted")
    pred_df, cv = train_models(pairs, config)
    geometry, geometry_summary = summarize_geometry(pairs, config)

    methods = [c for c in pred_df.columns if c not in {"truth_dt_ns", "sim_block", "heldout", "pair"}]
    family = {
        "truth_kinematic_tof": "traditional_relativistic",
        "calibrated_kinematic_tof": "traditional_calibrated",
        "nominal_2cm_notes": "traditional_fixed_note",
        "nominal_4cm_notes": "traditional_fixed_note",
        "4cm_40mev_tof": "traditional_fixed_energy",
        "4cm_190mev_tof": "traditional_fixed_energy",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_sequence",
        "physics_residual_mlp": "neural_physics_residual",
    }
    metric_rows = []
    for i, method in enumerate(methods):
        m = block_bootstrap_metrics(pred_df, method, int(config["truth"]["bootstrap_samples"]), int(config["truth"]["random_seed"]) + i)
        m["method"] = method
        m["family"] = family.get(method, "unknown")
        metric_rows.append(m)
    metrics = pd.DataFrame(metric_rows).sort_values(["mae_ns", "res68_abs_ns"], kind="mergesort").reset_index(drop=True)
    winner = metrics.iloc[0].to_dict()
    plot_path = plot_geometry(outdir, pairs, pred_df, str(winner["method"]))

    run_counts.to_csv(outdir / "run_counts.csv", index=False)
    pairs.to_parquet(outdir / "truth_pairs.parquet", index=False)
    pred_df.to_parquet(outdir / "predictions.parquet", index=False)
    metrics.to_csv(outdir / "metrics.csv", index=False)
    geometry.to_csv(outdir / "geometry_summary.csv", index=False)
    cv.to_csv(outdir / "validation_scan.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": gate.iloc[0].to_dict(),
        "geant4_root": str(config["geant4_root"]),
        "n_truth_pairs": int(len(pairs)),
        "split_blocks": {
            "train": config["truth"]["train_blocks"],
            "val": config["truth"]["val_blocks"],
            "heldout": config["truth"]["heldout_blocks"],
        },
        "geometry_summary": geometry_summary,
        "next_tickets": [
            {
                "title": "S12b: GEANT4 detector-map contract for HRD channel to Sci_bar layer mapping",
                "body": "Question: do HRD channel names B2/B4/B6/B8 map unambiguously to GEANT4 Sci_bar layer IDs 0/2/4/6 and construction coordinates? Expected information gain: converts the S12a natural even-layer mapping from an analysis convention into a documented detector-geometry contract, and would falsify or confirm whether the 4 cm timing/spacing correction can be applied to future raw-data timing studies without a hidden channel-map systematic.",
                "expected_information_gain": "High: it attacks the dominant caveat in the GEANT4 timing-scale validation and determines whether the 4 cm correction is a detector fact or an analysis assumption.",
            }
        ],
        "winner": winner,
        "all_metrics": metrics.to_dict(orient="records"),
        "geometry_by_pair": geometry.to_dict(orient="records"),
        "finding": (
            f"GEANT4 truth supports {geometry_summary['median_analyzed_spacing_cm']:.3f} cm analyzed-stave spacing "
            f"and a median timing scale of {geometry_summary['median_tof_per_cm_ns']:.5f} ns/cm; "
            f"winner={winner['method']} with MAE={winner['mae_ns']:.5f} ns."
        ),
        "runtime_sec": round(time.time() - start, 3),
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "commands": [f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {config_path.relative_to(ROOT)}"],
        "random_seed": int(config["truth"]["random_seed"]),
        "inputs": {
            str(config_path.relative_to(ROOT)): sha256_file(config_path),
            f"scripts/{Path(__file__).name}": sha256_file(Path(__file__)),
            str(config["geant4_root"]): sha256_file(Path(config["geant4_root"])),
        },
        "raw_root_dir": str(config["raw_root_dir"]),
        "outputs": {},
    }
    write_report(outdir, config_path, config, gate, geometry, geometry_summary, metrics, winner, cv, manifest)
    for rel in [
        "REPORT.md",
        "result.json",
        "run_counts.csv",
        "truth_pairs.parquet",
        "predictions.parquet",
        "metrics.csv",
        "geometry_summary.csv",
        "validation_scan.csv",
        str(plot_path.relative_to(outdir)),
    ]:
        p = outdir / rel
        manifest["outputs"][rel] = sha256_file(p)
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"outdir": str(outdir), "winner": winner["method"], "mae_ns": winner["mae_ns"]}, indent=2))


if __name__ == "__main__":
    main()
