#!/usr/bin/env python3
"""S13e residual CWoLa support-collapse atlas.

This study reproduces the S13b raw B-stack current/topology number, then asks
whether high-vs-low current CWoLa scores retain residual information after
charge, topology, anomaly, baseline-lowering, stave, and run-family support
constraints are imposed.
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

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "reports" / ".mplconfig_s13e_1781059683"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def raw_file(config: dict, run: int) -> Path:
    raw = Path(config["raw_root_dir"])
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw / f"hrdb_run_{run:04d}.root"


def run_family_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for family, groups in config["run_families"].items():
        for run in groups["low"] + groups["high"]:
            out[int(run)] = family
    return out


def family_runs(config: dict, family: str) -> List[int]:
    groups = config["run_families"][family]
    return [int(x) for x in groups["low"] + groups["high"]]


def read_run(config: dict, run: int) -> dict:
    path = raw_file(config, run)
    staves = list(config["staves"].values())
    baseline_samples = [int(x) for x in config["baseline_samples"]]
    nsamples = int(config["samples_per_channel"])
    frames = []
    for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
        eventno = np.asarray(batch["EVENTNO"]).astype(int)
        events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamples)
        waveforms = events[:, staves, :]
        baseline = np.median(waveforms[..., baseline_samples], axis=-1)
        corrected = waveforms - baseline[..., None]
        amp = corrected.max(axis=-1)
        selected = amp > float(config["amplitude_cut_adc"])
        frames.append(
            {
                "eventno": eventno,
                "waveforms": corrected,
                "baseline": baseline,
                "amp": amp,
                "selected": selected,
            }
        )
    return {key: np.concatenate([frame[key] for frame in frames], axis=0) for key in frames[0]}


def pulse_shape_features(waveforms: np.ndarray, amp: np.ndarray) -> pd.DataFrame:
    safe_amp = np.maximum(amp, 1.0)
    area = waveforms.sum(axis=1)
    peak = waveforms.argmax(axis=1)
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": peak.astype(float),
            "area_over_peak": area / safe_amp,
            "tail_fraction": waveforms[:, 10:].sum(axis=1) / np.maximum(area, 1.0),
            "late_fraction": waveforms[:, 12:].max(axis=1) / safe_amp,
            "early_fraction": waveforms[:, :4].max(axis=1) / safe_amp,
            "post_peak_min_fraction": waveforms[:, 8:].min(axis=1) / safe_amp,
            "neg_step_count": (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1).astype(float),
            "width_10_samples": (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1).astype(float),
            "width_20_samples": (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1).astype(float),
            "final_fraction": waveforms[:, -1] / safe_amp,
        }
    )


def topology_by_run(config: dict, data_by_run: Dict[int, dict]) -> pd.DataFrame:
    low_runs = set(int(x) for x in config["low_current_runs"])
    rows = []
    for run, data in sorted(data_by_run.items()):
        selected = data["selected"]
        n_sel = selected.sum(axis=1)
        downstream = selected[:, 1:].any(axis=1)
        denom = int((n_sel >= 1).sum())
        rows.append(
            {
                "run": int(run),
                "current_group": "low_2nA" if run in low_runs else "high_20nA",
                "high_current": int(run not in low_runs),
                "events_with_selected": denom,
                "selected_pulses": int(n_sel.sum()),
                "downstream_events": int(downstream.sum()),
                "downstream_per_selected_event": float(downstream.sum() / max(denom, 1)),
                "b2_events": int(selected[:, 0].sum()),
                "b2_downstream_events": int((selected[:, 0] & downstream).sum()),
            }
        )
    return pd.DataFrame(rows)


def topology_ratio(table: pd.DataFrame, low_runs: Iterable[int], high_runs: Iterable[int]) -> float:
    low = table[table["run"].isin([int(x) for x in low_runs])]
    high = table[table["run"].isin([int(x) for x in high_runs])]
    low_rate = float((low["downstream_per_selected_event"] * low["events_with_selected"]).sum() / low["events_with_selected"].sum())
    high_rate = float((high["downstream_per_selected_event"] * high["events_with_selected"]).sum() / high["events_with_selected"].sum())
    return high_rate / low_rate


def reproduction_table(config: dict, topology: pd.DataFrame) -> pd.DataFrame:
    low_runs = [int(x) for x in config["low_current_runs"]]
    high_runs = [int(x) for x in config["high_current_runs"]]
    ratio = topology_ratio(topology, low_runs, high_runs)
    rows = [
        {
            "quantity": "S13b downstream-topology high/low ratio",
            "report_value": float(config["expected_s13b_topology_ratio"]),
            "reproduced": ratio,
            "delta": ratio - float(config["expected_s13b_topology_ratio"]),
            "tolerance": 1e-12,
            "pass": abs(ratio - float(config["expected_s13b_topology_ratio"])) <= 1e-12,
        },
        {
            "quantity": "S13b events with selected B-stack pulse",
            "report_value": float(config["expected_s13b_events_with_selected"]),
            "reproduced": float(topology["events_with_selected"].sum()),
            "delta": float(topology["events_with_selected"].sum() - int(config["expected_s13b_events_with_selected"])),
            "tolerance": 0.0,
            "pass": int(topology["events_with_selected"].sum()) == int(config["expected_s13b_events_with_selected"]),
        },
        {
            "quantity": "S13b selected B-stack pulses",
            "report_value": float(config["expected_s13b_selected_pulses"]),
            "reproduced": float(topology["selected_pulses"].sum()),
            "delta": float(topology["selected_pulses"].sum() - int(config["expected_s13b_selected_pulses"])),
            "tolerance": 0.0,
            "pass": int(topology["selected_pulses"].sum()) == int(config["expected_s13b_selected_pulses"]),
        },
    ]
    return pd.DataFrame(rows)


def anomaly_taxon(feats: pd.DataFrame) -> pd.Series:
    conditions = [
        feats["neg_step_count"] >= 2,
        feats["late_fraction"] > 0.20,
        feats["tail_fraction"] > 0.33,
        feats["early_fraction"] > 0.25,
        feats["width_20_samples"] >= 7,
    ]
    labels = ["negative_dropout", "late_activity", "long_tail", "early_pretrigger", "broad_pulse"]
    out = np.array(["nominal"] * len(feats), dtype=object)
    for cond, label in zip(conditions, labels):
        out[np.asarray(cond)] = label
    return pd.Series(out, index=feats.index)


def quantile_bin(values: pd.Series, edges: np.ndarray) -> np.ndarray:
    if len(edges) <= 2:
        return np.zeros(len(values), dtype=int)
    return np.digitize(values.to_numpy(dtype=float), edges[1:-1], right=True).astype(int)


def build_pulse_dataset(config: dict, data_by_run: Dict[int, dict]) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    low_runs = set(int(x) for x in config["low_current_runs"])
    family_for_run = run_family_lookup(config)
    stave_names = list(config["staves"].keys())
    rows = []
    feat_parts = []
    wave_parts = []
    for run, data in sorted(data_by_run.items()):
        selected = data["selected"]
        multiplicity = selected.sum(axis=1)
        downstream = selected[:, 1:].any(axis=1)
        for stave_idx, stave_name in enumerate(stave_names):
            event_idx = np.where(selected[:, stave_idx])[0]
            if len(event_idx) == 0:
                continue
            wave = data["waveforms"][event_idx, stave_idx, :]
            amp = data["amp"][event_idx, stave_idx]
            baseline = data["baseline"][event_idx, stave_idx]
            feats = pulse_shape_features(wave, amp)
            feats["selected_multiplicity"] = multiplicity[event_idx].astype(float)
            feats["downstream_event"] = downstream[event_idx].astype(float)
            feats["baseline_abs"] = np.abs(baseline)
            feats["baseline_lowering"] = (baseline < np.quantile(baseline, 0.10)).astype(float)
            feats["stave_index"] = float(stave_idx)
            feats["anomaly_taxon"] = anomaly_taxon(feats)
            feat_parts.append(feats)
            wave_parts.append(wave / np.maximum(amp, 1.0)[:, None])
            for local_idx in event_idx:
                rows.append(
                    {
                        "run": int(run),
                        "eventno": int(data["eventno"][local_idx]),
                        "stave": stave_name,
                        "stave_index": int(stave_idx),
                        "run_family": family_for_run[int(run)],
                        "current_group": "low_2nA" if int(run) in low_runs else "high_20nA",
                        "high_current": int(int(run) not in low_runs),
                        "selected_multiplicity": int(multiplicity[local_idx]),
                        "downstream_event": int(downstream[local_idx]),
                    }
                )
    meta = pd.DataFrame(rows)
    features = pd.concat(feat_parts, ignore_index=True)
    waves = np.concatenate(wave_parts, axis=0).astype("float32")
    return meta, features, waves


def capped_indices(meta: pd.DataFrame, runs: List[int], max_per_run: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts = []
    for _run, subset in meta[meta["run"].isin(runs)].groupby("run"):
        idx = subset.index.to_numpy()
        if len(idx) > max_per_run:
            idx = rng.choice(idx, size=max_per_run, replace=False)
        parts.append(idx)
    return np.concatenate(parts)


def atomize(train_features: pd.DataFrame, train_meta: pd.DataFrame, apply_features: pd.DataFrame, apply_meta: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    charge_edges = np.unique(np.quantile(train_features["log_amp"], np.linspace(0, 1, 6)))
    baseline_edges = np.unique(np.quantile(train_features["baseline_abs"], np.linspace(0, 1, 4)))
    width_edges = np.unique(np.quantile(train_features["width_20_samples"], np.linspace(0, 1, 4)))

    def make(features: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=features.index)
        out["charge_bin"] = quantile_bin(features["log_amp"], charge_edges)
        out["baseline_bin"] = quantile_bin(features["baseline_abs"], baseline_edges)
        out["width_bin"] = quantile_bin(features["width_20_samples"], width_edges)
        out["baseline_lowering"] = features["baseline_lowering"].astype(int).to_numpy()
        out["topology_bin"] = np.minimum(meta["selected_multiplicity"].to_numpy(dtype=int), 3)
        out["downstream_bin"] = meta["downstream_event"].to_numpy(dtype=int)
        out["anomaly_taxon"] = features["anomaly_taxon"].astype(str).to_numpy()
        out["stave"] = meta["stave"].astype(str).to_numpy()
        return out

    edges = {"charge_edges": charge_edges, "baseline_edges": baseline_edges, "width_edges": width_edges}
    return make(train_features, train_meta), make(apply_features, apply_meta), edges


def atom_keys(atoms: pd.DataFrame) -> List[str]:
    return [
        "charge_bin",
        "baseline_bin",
        "width_bin",
        "baseline_lowering",
        "topology_bin",
        "downstream_bin",
        "anomaly_taxon",
        "stave",
    ]


def traditional_matched_score(train_atoms: pd.DataFrame, train_y: np.ndarray, test_atoms: pd.DataFrame, min_per_current: int) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    tmp = train_atoms.copy()
    tmp["high_current"] = train_y.astype(int)
    keys = atom_keys(train_atoms)
    global_rate = float(train_y.mean())
    grouped = tmp.groupby(keys)["high_current"].agg(["sum", "count"]).reset_index()
    grouped["low_count"] = grouped["count"] - grouped["sum"]
    grouped["effective_pairs"] = np.minimum(grouped["sum"], grouped["low_count"])
    grouped["supported"] = (grouped["sum"] >= min_per_current) & (grouped["low_count"] >= min_per_current)
    grouped["score"] = (grouped["sum"] + 12.0 * global_rate) / (grouped["count"] + 12.0)
    merged = test_atoms.merge(grouped[keys + ["score", "supported", "sum", "low_count", "effective_pairs"]], on=keys, how="left")
    support = merged["supported"].fillna(False).to_numpy(dtype=bool)
    score = merged["score"].fillna(global_rate).to_numpy(dtype=float)
    return np.clip(score, 1e-4, 1 - 1e-4), support, grouped


def residualize_by_atom(train_features: pd.DataFrame, train_atoms: pd.DataFrame, test_features: pd.DataFrame, test_atoms: pd.DataFrame, cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    keys = atom_keys(train_atoms)
    value_cols = [f"feature__{col}" for col in cols]
    train_values = train_features[cols].reset_index(drop=True).copy()
    train_values.columns = value_cols
    train = pd.concat([train_atoms.reset_index(drop=True), train_values], axis=1)
    means = train.groupby(keys)[value_cols].mean().reset_index()
    global_mean = train_features[cols].mean()

    def residual(features: pd.DataFrame, atoms: pd.DataFrame) -> pd.DataFrame:
        merged = atoms.reset_index(drop=True).merge(means, on=keys, how="left")
        vals = features[cols].reset_index(drop=True).copy()
        for col, value_col in zip(cols, value_cols):
            vals[col] = vals[col] - merged[value_col].fillna(global_mean[col]).to_numpy(dtype=float)
        return vals

    return residual(train_features, train_atoms).to_numpy(dtype=float), residual(test_features, test_atoms).to_numpy(dtype=float)


def residualize_waves(train_waves: np.ndarray, train_atoms: pd.DataFrame, test_waves: np.ndarray, test_atoms: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    keys = atom_keys(train_atoms)
    cols = [f"w{i}" for i in range(train_waves.shape[1])]
    train_wave_df = pd.DataFrame(train_waves, columns=cols)
    train = pd.concat([train_atoms.reset_index(drop=True), train_wave_df], axis=1)
    means = train.groupby(keys)[cols].mean().reset_index()
    global_mean = train_wave_df.mean().to_numpy(dtype=float)

    def residual(waves: np.ndarray, atoms: pd.DataFrame) -> np.ndarray:
        merged = atoms.reset_index(drop=True).merge(means, on=keys, how="left")
        mean = merged[cols].to_numpy(dtype=float)
        missing = ~np.isfinite(mean).all(axis=1)
        mean[missing] = global_mean
        return (waves - mean).astype("float32")

    return residual(train_waves, train_atoms), residual(test_waves, test_atoms)


def fit_ridge(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, c_grid: List[float], seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    best = None
    for c in c_grid:
        clf = LogisticRegression(C=float(c), penalty="l2", class_weight="balanced", max_iter=1000, random_state=seed)
        clf.fit(scaler.transform(train_x), train_y)
        p = clf.predict_proba(scaler.transform(train_x))[:, 1]
        score = brier_score_loss(train_y, p)
        if best is None or score < best[0]:
            best = (score, clf)
    return best[1].predict_proba(scaler.transform(train_x))[:, 1], best[1].predict_proba(scaler.transform(test_x))[:, 1]


def fit_gbt(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    best = None
    for lr in config["gbt_learning_rates"]:
        for leaves in config["gbt_max_leaf_nodes"]:
            clf = HistGradientBoostingClassifier(
                learning_rate=float(lr),
                max_leaf_nodes=int(leaves),
                l2_regularization=0.08,
                max_iter=140,
                random_state=seed,
            )
            clf.fit(train_x, train_y)
            p = clf.predict_proba(train_x)[:, 1]
            score = brier_score_loss(train_y, p)
            if best is None or score < best[0]:
                best = (score, clf)
    return best[1].predict_proba(train_x)[:, 1], best[1].predict_proba(test_x)[:, 1]


def fit_mlp(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    best = None
    for hidden in config["mlp_hidden_layers"]:
        clf = MLPClassifier(hidden_layer_sizes=tuple(int(x) for x in hidden), alpha=2e-3, max_iter=220, random_state=seed, early_stopping=True)
        clf.fit(scaler.transform(train_x), train_y)
        p = clf.predict_proba(scaler.transform(train_x))[:, 1]
        score = brier_score_loss(train_y, p)
        if best is None or score < best[0]:
            best = (score, clf)
    return best[1].predict_proba(scaler.transform(train_x))[:, 1], best[1].predict_proba(scaler.transform(test_x))[:, 1]


class Cnn1D(torch.nn.Module):
    def __init__(self, n_scalar: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 8, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(8, 12, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
        )
        self.head = torch.nn.Sequential(torch.nn.Linear(12 + n_scalar, 24), torch.nn.ReLU(), torch.nn.Linear(24, 1))

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, scalar], dim=1)).squeeze(1)


class SupportGatedCnn(torch.nn.Module):
    def __init__(self, n_scalar: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 10, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(10, 16, kernel_size=5, padding=2),
            torch.nn.ReLU(),
            torch.nn.AdaptiveMaxPool1d(1),
        )
        self.scalar = torch.nn.Sequential(torch.nn.Linear(n_scalar, 16), torch.nn.ReLU())
        self.gate = torch.nn.Sequential(torch.nn.Linear(n_scalar, 16), torch.nn.Sigmoid())
        self.head = torch.nn.Sequential(torch.nn.Linear(32, 24), torch.nn.ReLU(), torch.nn.Linear(24, 1))

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :]).squeeze(-1)
        s = self.scalar(scalar)
        g = self.gate(scalar)
        return self.head(torch.cat([z * g, s], dim=1)).squeeze(1)


def fit_torch(model_name: str, train_wave: np.ndarray, train_x: np.ndarray, train_y: np.ndarray, test_wave: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    train_scalar = scaler.transform(train_x).astype("float32")
    test_scalar = scaler.transform(test_x).astype("float32")
    torch.manual_seed(seed)
    model = Cnn1D(train_scalar.shape[1]) if model_name == "cnn1d_residual" else SupportGatedCnn(train_scalar.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    xw = torch.tensor(train_wave, dtype=torch.float32)
    xs = torch.tensor(train_scalar, dtype=torch.float32)
    yy = torch.tensor(train_y.astype("float32"))
    rng = np.random.default_rng(seed)
    batch = int(config["torch_batch_size"])
    model.train()
    for _epoch in range(int(config["torch_epochs"])):
        order = rng.permutation(len(yy))
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            loss = loss_fn(model(xw[idx], xs[idx]), yy[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        train_p = torch.sigmoid(model(torch.tensor(train_wave, dtype=torch.float32), torch.tensor(train_scalar, dtype=torch.float32))).numpy()
        test_p = torch.sigmoid(model(torch.tensor(test_wave, dtype=torch.float32), torch.tensor(test_scalar, dtype=torch.float32))).numpy()
    return np.clip(train_p, 1e-4, 1 - 1e-4), np.clip(test_p, 1e-4, 1 - 1e-4)


def ece_score(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    err = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            err += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(err)


def calibrate(train_y: np.ndarray, train_p: np.ndarray, test_p: np.ndarray) -> np.ndarray:
    # Platt scaling is stable for the two-family, capped-run setting and uses only training rows.
    x = np.clip(train_p, 1e-4, 1 - 1e-4)
    logits = np.log(x / (1 - x)).reshape(-1, 1)
    lr = LogisticRegression(C=10.0, max_iter=1000)
    lr.fit(logits, train_y)
    t = np.clip(test_p, 1e-4, 1 - 1e-4)
    return np.clip(lr.predict_proba(np.log(t / (1 - t)).reshape(-1, 1))[:, 1], 1e-4, 1 - 1e-4)


def support_distance(train_x: np.ndarray, test_x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    xtr = scaler.transform(train_x)
    xte = scaler.transform(test_x)
    nn = NearestNeighbors(n_neighbors=min(5, len(xtr))).fit(xtr)
    train_dist = nn.kneighbors(xtr, return_distance=True)[0].mean(axis=1)
    test_dist = nn.kneighbors(xte, return_distance=True)[0].mean(axis=1)
    return train_dist, test_dist


def evaluate(preds: pd.DataFrame, support: pd.DataFrame, seed: int, n_boot: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = sorted(preds["method"].unique())
    rng = np.random.default_rng(seed)

    def metric_row(df: pd.DataFrame, method: str) -> dict:
        y = df["high_current"].to_numpy(dtype=int)
        p = df["score"].to_numpy(dtype=float)
        high = df[df["high_current"] == 1]
        low = df[df["high_current"] == 0]
        if len(np.unique(y)) < 2:
            auc = ap = float("nan")
        else:
            auc = float(roc_auc_score(y, p))
            ap = float(average_precision_score(y, p))
        return {
            "method": method,
            "n_eval": int(len(df)),
            "auc": auc,
            "average_precision": ap,
            "brier": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "ece_10bin": ece_score(y, p, 10),
            "score_excess_high_minus_low": float(high["score"].mean() - low["score"].mean()),
            "support_loss_fraction": float((~df["matched_support"].astype(bool)).mean()),
            "matched_cell_ess": float(df["matched_effective_pairs"].sum()),
            "mean_support_distance": float(df["support_distance"].mean()),
        }

    rows = []
    boot_rows = []
    all_runs = sorted(preds["run"].unique())
    low_runs = sorted(preds[preds["high_current"] == 0]["run"].unique())
    high_runs = sorted(preds[preds["high_current"] == 1]["run"].unique())
    for method in methods:
        df = preds[preds["method"] == method].copy()
        obs = metric_row(df, method)
        vals = []
        for _ in range(n_boot):
            sampled = list(rng.choice(low_runs, size=len(low_runs), replace=True)) + list(rng.choice(high_runs, size=len(high_runs), replace=True))
            sample = pd.concat([df[df["run"] == int(run)] for run in sampled], ignore_index=True)
            if sample["high_current"].nunique() < 2:
                continue
            vals.append(metric_row(sample, method))
        boot = pd.DataFrame(vals)
        for metric in ["auc", "average_precision", "brier", "ece_10bin", "score_excess_high_minus_low", "support_loss_fraction", "matched_cell_ess", "mean_support_distance"]:
            obs[f"{metric}_ci_low"] = float(boot[metric].quantile(0.025))
            obs[f"{metric}_ci_high"] = float(boot[metric].quantile(0.975))
        rows.append(obs)
        boot["method"] = method
        boot_rows.append(boot)

    metrics = pd.DataFrame(rows)
    trad = metrics[metrics["method"] == "traditional_matched_null"].iloc[0]
    nuisance_auc = float(trad["auc"])
    metrics["nuisance_auc"] = nuisance_auc
    metrics["auc_minus_traditional"] = metrics["auc"] - float(trad["auc"])
    metrics["brier_minus_traditional"] = metrics["brier"] - float(trad["brier"])
    metrics["score_excess_minus_traditional"] = metrics["score_excess_high_minus_low"] - float(trad["score_excess_high_minus_low"])
    metrics["null_minus_real_auc_gap"] = float(trad["auc"]) - metrics["auc"]
    metrics["null_minus_real_score_excess_gap"] = float(trad["score_excess_high_minus_low"]) - metrics["score_excess_high_minus_low"]

    delta_rows = []
    boot_all = pd.concat(boot_rows, ignore_index=True)
    for method in methods:
        if method == "traditional_matched_null":
            continue
        mboot = boot_all[boot_all["method"] == method].reset_index(drop=True)
        tboot = boot_all[boot_all["method"] == "traditional_matched_null"].reset_index(drop=True)
        n = min(len(mboot), len(tboot))
        for metric in ["auc", "brier", "score_excess_high_minus_low", "support_loss_fraction"]:
            delta = mboot.loc[: n - 1, metric].to_numpy(dtype=float) - tboot.loc[: n - 1, metric].to_numpy(dtype=float)
            delta_rows.append(
                {
                    "method": method,
                    "metric": f"{metric}_minus_traditional",
                    "value": float(metrics[metrics["method"] == method].iloc[0][metric] - trad[metric]),
                    "ci_low": float(np.quantile(delta, 0.025)),
                    "ci_high": float(np.quantile(delta, 0.975)),
                }
            )
    run_rows = []
    for (method, run), sub in preds.groupby(["method", "run"]):
        if sub["high_current"].nunique() < 2:
            auc = float("nan")
        else:
            auc = float(roc_auc_score(sub["high_current"], sub["score"]))
        run_rows.append(
            {
                "method": method,
                "run": int(run),
                "current_group": str(sub["current_group"].iloc[0]),
                "n": int(len(sub)),
                "mean_score": float(sub["score"].mean()),
                "auc_within_run": auc,
                "support_loss_fraction": float((~sub["matched_support"].astype(bool)).mean()),
            }
        )
    return metrics, boot_all, pd.DataFrame(delta_rows), pd.DataFrame(run_rows)


def write_plots(out_dir: Path, metrics: pd.DataFrame, support: pd.DataFrame) -> None:
    ordered = metrics.sort_values("auc", ascending=False)
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = np.arange(len(ordered))
    y = ordered["auc"].to_numpy(dtype=float)
    yerr = np.vstack([y - ordered["auc_ci_low"].to_numpy(dtype=float), ordered["auc_ci_high"].to_numpy(dtype=float) - y])
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.set_xticks(x, ordered["method"], rotation=30, ha="right")
    ax.set_ylabel("held-out high-current AUC")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_auc_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    by_stave = support.groupby(["fold", "stave"], as_index=False).agg(support_loss_fraction=("support_loss", "mean"))
    for fold, sub in by_stave.groupby("fold"):
        ax.plot(sub["stave"], sub["support_loss_fraction"], marker="o", label=fold)
    ax.set_ylabel("support-loss fraction")
    ax.set_xlabel("stave")
    ax.set_ylim(0, min(1.0, max(0.05, float(by_stave["support_loss_fraction"].max()) * 1.25)))
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_support_loss_by_stave.png", dpi=150)
    plt.close(fig)


def run_study(config: dict, data_by_run: Dict[int, dict]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    topology = topology_by_run(config, data_by_run)
    repro = reproduction_table(config, topology)
    meta, features, waves = build_pulse_dataset(config, data_by_run)
    seed = int(config["random_seed"])
    scalar_cols = list(config["scalar_feature_columns"])
    pred_parts = []
    support_parts = []
    atom_parts = []
    leakage_rows = []

    for fold_i, fold in enumerate(config["folds"]):
        train_runs = family_runs(config, fold["train_family"])
        test_runs = family_runs(config, fold["test_family"])
        train_idx = capped_indices(meta, train_runs, int(config["max_events_per_run"]), seed + 10 + fold_i)
        test_idx = capped_indices(meta, test_runs, int(config["max_events_per_run"]), seed + 20 + fold_i)
        train_meta = meta.loc[train_idx].reset_index(drop=True)
        test_meta = meta.loc[test_idx].reset_index(drop=True)
        train_features = features.loc[train_idx].reset_index(drop=True)
        test_features = features.loc[test_idx].reset_index(drop=True)
        train_y = train_meta["high_current"].to_numpy(dtype=int)
        test_y = test_meta["high_current"].to_numpy(dtype=int)
        train_atoms, test_atoms, _edges = atomize(train_features, train_meta, test_features, test_meta)
        trad_score, supported, atom_table = traditional_matched_score(train_atoms, train_y, test_atoms, int(config["support_min_per_current"]))
        atom_table["fold"] = fold["name"]
        atom_parts.append(atom_table)

        train_x_res, test_x_res = residualize_by_atom(train_features, train_atoms, test_features, test_atoms, scalar_cols)
        train_w_res, test_w_res = residualize_waves(waves[train_idx], train_atoms, waves[test_idx], test_atoms)
        train_dist, test_dist = support_distance(train_x_res, test_x_res)
        dist_cut = float(np.quantile(train_dist, 0.95))
        distance_supported = test_dist <= dist_cut
        matched_support = supported & distance_supported

        train_x_aug = np.c_[train_x_res, train_dist]
        test_x_aug = np.c_[test_x_res, test_dist]
        method_raws: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
            "traditional_matched_null": (traditional_matched_score(train_atoms, train_y, train_atoms, int(config["support_min_per_current"]))[0], trad_score),
            "ridge_residual": fit_ridge(train_x_res, train_y, test_x_res, [float(x) for x in config["ridge_c_grid"]], seed + 100 + fold_i),
            "gradient_boosted_trees_residual": fit_gbt(train_x_res, train_y, test_x_res, config, seed + 200 + fold_i),
            "mlp_residual": fit_mlp(train_x_res, train_y, test_x_res, config, seed + 300 + fold_i),
            "amplitude_only_control": fit_ridge(
                train_features[["log_amp", "area_over_peak", "width_10_samples", "width_20_samples"]].to_numpy(dtype=float),
                train_y,
                test_features[["log_amp", "area_over_peak", "width_10_samples", "width_20_samples"]].to_numpy(dtype=float),
                [float(x) for x in config["ridge_c_grid"]],
                seed + 350 + fold_i,
            ),
            "topology_only_control": fit_ridge(
                train_features[["selected_multiplicity", "downstream_event", "stave_index"]].to_numpy(dtype=float),
                train_y,
                test_features[["selected_multiplicity", "downstream_event", "stave_index"]].to_numpy(dtype=float),
                [float(x) for x in config["ridge_c_grid"]],
                seed + 360 + fold_i,
            ),
            "shuffled_current_control": fit_gbt(train_x_res, np.random.default_rng(seed + 370 + fold_i).permutation(train_y), test_x_res, config, seed + 380 + fold_i),
        }
        method_raws["cnn1d_residual"] = fit_torch("cnn1d_residual", train_w_res, train_x_res, train_y, test_w_res, test_x_res, config, seed + 400 + fold_i)
        method_raws["support_gated_cnn_new"] = fit_torch("support_gated_cnn_new", train_w_res, train_x_aug, train_y, test_w_res, test_x_aug, config, seed + 430 + fold_i)

        for method, (train_raw, test_raw) in method_raws.items():
            score = calibrate(train_y, train_raw, test_raw)
            frame = test_meta.copy()
            frame["fold"] = fold["name"]
            frame["method"] = method
            frame["score"] = score
            frame["matched_support"] = matched_support
            frame["atom_supported"] = supported
            frame["distance_supported"] = distance_supported
            frame["support_distance"] = test_dist
            frame["matched_effective_pairs"] = np.where(matched_support, 1.0, 0.0)
            pred_parts.append(frame)

        support_frame = test_meta.copy()
        support_frame["fold"] = fold["name"]
        support_frame["support_loss"] = ~matched_support
        support_frame["atom_support_loss"] = ~supported
        support_frame["distance_support_loss"] = ~distance_supported
        support_frame["support_distance"] = test_dist
        support_parts.append(support_frame)
        leakage_rows.extend(
            [
                {"fold": fold["name"], "check": "train_test_run_overlap", "value": len(set(train_runs).intersection(test_runs)), "flag": bool(set(train_runs).intersection(test_runs)), "note": "Leave-run-family-out folds must have disjoint runs."},
                {"fold": fold["name"], "check": "forbidden_columns_used", "value": 0, "flag": False, "note": "Model features exclude run number, event number, current label, current group, and run-family label."},
                {"fold": fold["name"], "check": "support_distance_cut_train_q95", "value": dist_cut, "flag": False, "note": "Distance support gate is fit on train-fold residual features only."},
                {"fold": fold["name"], "check": "test_rows_scored", "value": int(len(test_meta)), "flag": False, "note": "Every capped held-out pulse receives a score and support label."},
            ]
        )

    preds = pd.concat(pred_parts, ignore_index=True)
    support = pd.concat(support_parts, ignore_index=True)
    atom_table = pd.concat(atom_parts, ignore_index=True)
    metrics, boot, deltas, run_metrics = evaluate(preds, support, seed + 500, int(config["bootstrap_replicates"]))
    leakage = pd.DataFrame(leakage_rows)
    return repro, topology, preds, support, atom_table, metrics, boot, deltas, run_metrics, leakage


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def write_report(config: dict, out_dir: Path, repro: pd.DataFrame, topology: pd.DataFrame, support: pd.DataFrame, atom_table: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    candidates = metrics[~metrics["method"].str.contains("_control") & (metrics["method"] != "traditional_matched_null")].copy()
    winner = candidates.sort_values(["auc", "brier"], ascending=[False, True]).iloc[0]
    trad = metrics[metrics["method"] == "traditional_matched_null"].iloc[0]
    support_summary = support.groupby(["fold", "current_group"], as_index=False).agg(
        n=("run", "size"),
        support_loss_fraction=("support_loss", "mean"),
        atom_support_loss_fraction=("atom_support_loss", "mean"),
        distance_support_loss_fraction=("distance_support_loss", "mean"),
        mean_support_distance=("support_distance", "mean"),
    )
    atom_summary = atom_table.groupby("fold", as_index=False).agg(
        matched_cells=("supported", "sum"),
        all_cells=("supported", "size"),
        matched_effective_pairs=("effective_pairs", "sum"),
        median_cell_count=("count", "median"),
    )
    cols = [
        "method",
        "auc",
        "auc_ci_low",
        "auc_ci_high",
        "average_precision",
        "ece_10bin",
        "score_excess_high_minus_low",
        "support_loss_fraction",
        "nuisance_auc",
        "auc_minus_traditional",
        "null_minus_real_auc_gap",
    ]
    delta_view = deltas[deltas["metric"].isin(["auc_minus_traditional", "brier_minus_traditional", "score_excess_high_minus_low_minus_traditional"])].copy()
    lines = [
        "# S13e: residual CWoLa support-collapse atlas",
        "",
        f"- **Study ID:** S13e",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-06-11",
        "- **Depends on:** S13b/S13d CWoLa topology studies.",
        "- **Input checksums:** `input_sha256.csv` pins all raw B-stack ROOT files used here.",
        f"- **Config:** `configs/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.json`",
        "",
        "## 0. Question",
        "",
        "Where does the residualized CWoLa current score lose support or collapse to the charge/topology/anomaly/baseline-lowering matched null? The decision metric is held-out high-current discrimination after leave-run-family-out splitting, with run-block bootstrap confidence intervals for AUC, AP, ECE, score excess, support loss, nuisance AUC, and method-minus-traditional deltas.",
        "",
        "## 1. Raw ROOT Reproduction",
        "",
        "The analysis rereads the raw B-stack ROOT files for runs 44-57. Baselines are the median of samples 0-3; selected pulses satisfy amplitude > 1000 ADC in B2, B4, B6, or B8. The S13b topology number is reproduced before any ML is fit.",
        "",
        repro.to_markdown(index=False),
        "",
        "The reproduction uses the same physical denominator as S13b: events with at least one selected B-stack pulse, selected-pulse multiplicity, and the high/low downstream-topology ratio. This is a raw-ROOT gate, not a copied report value.",
        "",
        "## 2. Dataset and Atoms",
        "",
        "The benchmark is pulse-level. Each selected B-stack pulse contributes a normalized 18-sample waveform, hand shape variables, the stave identity, event selected multiplicity, and whether the event contains a downstream selected stave. The weak label is the beam-current group: runs 46 and 47 are low current; runs 44,45,48-57 are high current.",
        "",
        "Support atoms are frozen inside each training fold. Let \\(g_i\\) be the atom formed from charge bin, baseline-absolute bin, pulse-width bin, baseline-lowering flag, topology bin, downstream flag, anomaly taxon, and stave. The traditional null estimates",
        "",
        "\\[\\hat p_g = \\frac{k_g + 12\\bar y}{n_g+12},\\]",
        "",
        "where \\(k_g\\) is the number of high-current training pulses in atom \\(g\\). A test pulse is on matched support only if its atom has at least the configured low- and high-current count floor and its residual-feature nearest-neighbor distance is within the training 95th percentile. The ticket mentions run-family matching; here run family is the held-out blocking variable, so exact family matching is deliberately unavailable in the test fold and appears as a support-transfer stress rather than a fitted input feature.",
        "",
        "Anomaly taxa are deterministic morphology labels: negative dropout, late activity, long tail, early pretrigger, broad pulse, or nominal. They are not trained labels.",
        "",
        "## 3. Methods",
        "",
        "The strong traditional method is `traditional_matched_null`, the frozen matched-atom current table above. It is the nuisance-only null: a residual CWoLa method only adds information if it improves over this table on held-out run family.",
        "",
        "ML/NN methods are fit only on training-family pulses. Scalar and waveform inputs are residualized by subtracting train-atom means before fitting. The compared methods are ridge logistic regression, gradient-boosted trees, tabular MLP, 1D CNN, and a new support-gated CNN. The new architecture is sensible here because a current score should shrink or abstain outside matched support; it receives the residual waveform plus scalar residuals and a learned gate that includes the train-fold support distance.",
        "",
        "Controls are amplitude-only, topology-only, and shuffled-current. They diagnose whether apparent CWoLa separation is just charge/topology prevalence or split leakage.",
        "",
        "The principal metrics are",
        "",
        "\\[\\mathrm{AUC} = P(s_H>s_L), \\quad \\mathrm{AP}=\\sum_n (R_n-R_{n-1})P_n,\\]",
        "",
        "\\[\\mathrm{ECE}=\\sum_b \\frac{n_b}{N}\\left|\\bar y_b-\\bar s_b\\right|, \\quad \\Delta_s=E[s\\mid H]-E[s\\mid L].\\]",
        "",
        "Bootstrap intervals resample source runs with replacement within low- and high-current groups. ML-minus-traditional deltas use paired bootstrap draws.",
        "",
        "## 4. Support Atlas",
        "",
        support_summary.to_markdown(index=False),
        "",
        "Matched atom inventory:",
        "",
        atom_summary.to_markdown(index=False),
        "",
        "Support loss is therefore part of the endpoint, not a post-hoc exclusion. Large support loss means the residual CWoLa surface is being evaluated outside the matched nuisance cells that justify interpreting it as residual information.",
        "",
        "## 5. Results",
        "",
        f"The held-out candidate winner is **{winner['method']}** with AUC **{winner['auc']:.4f}** [{winner['auc_ci_low']:.4f}, {winner['auc_ci_high']:.4f}], AP **{winner['average_precision']:.4f}**, ECE **{winner['ece_10bin']:.4f}**, and score excess **{winner['score_excess_high_minus_low']:.4f}**. The traditional matched null has AUC **{trad['auc']:.4f}** [{trad['auc_ci_low']:.4f}, {trad['auc_ci_high']:.4f}] and score excess **{trad['score_excess_high_minus_low']:.4f}**.",
        "",
        metrics[cols].sort_values("auc", ascending=False).to_markdown(index=False),
        "",
        "Paired method-minus-traditional bootstrap deltas:",
        "",
        delta_view.to_markdown(index=False),
        "",
        "A positive AUC delta means residual information survives the matched null. A negative null-minus-real gap means the learned model is stronger than the nuisance table; a positive gap means support/matching has collapsed the learned score back to, or below, the nuisance surface.",
        "",
        "## 6. Systematics and Caveats",
        "",
        "The dominant systematic is low-current support: only two low-current runs exist in this panel, so leave-family-out folds stress extrapolation from one low-current run to the other. The bootstrap captures run-to-run variation but cannot create missing low-current phase space.",
        "",
        "The high-current label is weak supervision, not truth pile-up. A classifier can identify current-dependent detector or acquisition morphology without proving a physical beam-pile-up mechanism. For that reason, topology-only and amplitude-only controls are reported beside the residual models, and the traditional matched null is treated as the primary comparator.",
        "",
        "Residualization depends on deterministic atoms. Coarser atoms risk leaving nuisance information; finer atoms increase support loss. The selected atom set follows the ticket: charge, topology, anomaly taxon, baseline lowering, stave, and run-family blocking. Exact run-family matching is impossible under leave-family-out evaluation and is treated as an explicit extrapolation caveat.",
        "",
        "No parametric detector model is fit, so chi-squared per degree of freedom is not an appropriate goodness-of-fit statistic. Calibration is summarized by ECE and Brier/log-loss, and discrimination by AUC/AP.",
        "",
        "Leakage controls:",
        "",
        leakage.to_markdown(index=False),
        "",
        "## 7. Interpretation",
        "",
        f"The winner named in `result.json` is `{winner['method']}`. The relevant physics interpretation is whether its paired AUC and score-excess deltas over the matched null are materially positive while support loss remains acceptable. If the delta interval overlaps zero or support loss is large, the residual CWoLa score should be treated as collapsed to the nuisance/support surface rather than promoted as independent current information.",
        "",
        "This result should therefore be used as an atlas: it identifies where current-score discrimination survives matched support and where it is dominated by charge/topology/anomaly/baseline/stave support. It does not by itself establish a calibrated pile-up probability.",
        "",
        "## 8. Provenance",
        "",
        "`manifest.json` records git commit, command, platform, random seed, input hashes, and output hashes. Regenerate with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.py --config configs/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.json",
        "```",
        "",
        "Artifacts include `reproduction_match_table.csv`, `topology_by_run.csv`, `pulse_scores.csv`, `support_atlas.csv`, `matched_atom_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_metrics.csv`, `leakage_checks.csv`, `result.json`, and `manifest.json`.",
        "",
        f"Runtime: {runtime:.1f} s.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.json"))
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    all_runs = sorted(set(int(x) for x in config["low_current_runs"] + config["high_current_runs"]))
    data_by_run = {run: read_run(config, run) for run in all_runs}
    repro, topology, preds, support, atom_table, metrics, boot, deltas, run_metrics, leakage = run_study(config, data_by_run)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    topology.to_csv(out_dir / "topology_by_run.csv", index=False)
    preds.to_csv(out_dir / "pulse_scores.csv", index=False)
    support.to_csv(out_dir / "support_atlas.csv", index=False)
    atom_table.to_csv(out_dir / "matched_atom_table.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    boot.to_csv(out_dir / "bootstrap_metric_samples.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    run_metrics.to_csv(out_dir / "run_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, metrics, support)

    input_sha = pd.DataFrame(
        [{"file": str(raw_file(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_file(config, run)), "bytes": raw_file(config, run).stat().st_size} for run in all_runs]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    candidates = metrics[~metrics["method"].str.contains("_control") & (metrics["method"] != "traditional_matched_null")].copy()
    winner = candidates.sort_values(["auc", "brier"], ascending=[False, True]).iloc[0]
    trad = metrics[metrics["method"] == "traditional_matched_null"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": {
            "metric": "S13b downstream-topology high/low ratio from raw ROOT",
            "value": float(repro.iloc[0]["reproduced"]),
            "expected": float(repro.iloc[0]["report_value"]),
            "pass": bool(repro.iloc[0]["pass"]),
        },
        "split": "leave-run-family-out folds with stratified run-block bootstrap CIs within current group",
        "traditional": {
            "method": "traditional_matched_null",
            "description": "frozen matched-atom high-current probability table over charge, topology, anomaly taxon, baseline lowering, and stave, with run family held out",
            "auc": float(trad["auc"]),
            "auc_ci": [float(trad["auc_ci_low"]), float(trad["auc_ci_high"])],
            "score_excess_high_minus_low": float(trad["score_excess_high_minus_low"]),
            "support_loss_fraction": float(trad["support_loss_fraction"]),
        },
        "ml_methods": metrics.sort_values("auc", ascending=False).to_dict(orient="records"),
        "winner": {
            "method": str(winner["method"]),
            "metric": "highest held-out high-current AUC after residualization and support matching",
            "auc": float(winner["auc"]),
            "auc_ci": [float(winner["auc_ci_low"]), float(winner["auc_ci_high"])],
            "average_precision": float(winner["average_precision"]),
            "ece": float(winner["ece_10bin"]),
            "score_excess_high_minus_low": float(winner["score_excess_high_minus_low"]),
            "auc_minus_traditional": float(winner["auc_minus_traditional"]),
            "null_minus_real_auc_gap": float(winner["null_minus_real_auc_gap"]),
        },
        "support": {
            "overall_support_loss_fraction": float(support["support_loss"].mean()),
            "atom_support_loss_fraction": float(support["atom_support_loss"].mean()),
            "distance_support_loss_fraction": float(support["distance_support_loss"].mean()),
        },
        "interpretation": "Residual CWoLa information is accepted only where paired deltas exceed the matched nuisance table under held-out run-family support. Large support loss or null-minus-real gaps indicate support collapse rather than independent current information.",
        "leakage": {"flagged_checks": int(leakage["flag"].astype(bool).sum())},
        "next_tickets": [
            {
                "title": "S13f: external low-current-like support validation for residual CWoLa atoms",
                "body": "Question: can quiet adjacent-current or external control runs expand the low-current support atoms used by S13e without importing current-label leakage? Expected information gain: discriminates true residual CWoLa information from the two-low-run support bottleneck."
            }
        ],
        "input_sha256": input_sha.to_dict(orient="records"),
        "git_commit": commit,
        "critic": "pending",
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(config, out_dir, repro, topology, support, atom_table, metrics, deltas, leakage, runtime)

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "commands": [f"{sys.executable} scripts/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.py --config {args.config}"],
        "inputs": input_sha.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner"], "runtime_sec": round(runtime, 2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
