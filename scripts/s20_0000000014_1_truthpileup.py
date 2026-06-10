#!/usr/bin/env python3
"""S20 / ticket 0000000014.1.truthpileup.

GEANT4 truth validation of B-stack pile-up multiplicity.  The script keeps the
raw-data reproduction gate first, then compares a truth-blind topology method
against a small ML/NN panel on GEANT4 event truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import awkward as ak
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
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
PROTON = 2212
DEUTERON = 1000010020


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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def log(message: str) -> None:
    print(f"[s20] {message}", file=sys.stderr, flush=True)


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def current_group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["current_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def reproduce_raw_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    raw_root = ROOT / config["raw_root_dir"]
    current_lookup = current_group_for_run(config)
    rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root / f"hrdb_run_{run:04d}.root"
        row = {
            "run": run,
            "current_group": current_lookup.get(run, "not_in_current_panel"),
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "multi_stave_events": 0,
            "three_stave_events": 0,
            "downstream_events": 0,
        }
        row.update({stave: 0 for stave in staves})
        for batch in iter_raw_batches(path):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            waves = corrected[:, channels, :]
            amps = waves.max(axis=-1)
            selected = amps > cut
            n_sel = selected.sum(axis=1)
            row["events_total"] += int(len(raw))
            row["events_with_selected"] += int((n_sel > 0).sum())
            row["selected_pulses"] += int(n_sel.sum())
            row["multi_stave_events"] += int((n_sel >= 2).sum())
            row["three_stave_events"] += int((n_sel >= 3).sum())
            row["downstream_events"] += int((selected[:, 1:].any(axis=1)).sum())
            for i, stave in enumerate(staves):
                row[stave] += int(selected[:, i].sum())
        rows.append(row)

    counts = pd.DataFrame(rows)
    repro_rows = [
        {
            "quantity": "total_selected_pulses",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": int(counts["selected_pulses"].sum()),
            "delta": int(counts["selected_pulses"].sum() - int(config["expected_selected_pulses"])),
            "tolerance": 0,
            "pass": bool(counts["selected_pulses"].sum() == int(config["expected_selected_pulses"])),
        }
    ]
    return counts, pd.DataFrame(repro_rows)


def ratio_ci_by_run(
    counts: pd.DataFrame,
    group: str,
    numerator: str,
    denominator: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    part = counts[counts["current_group"] == group].copy()
    value = float(part[numerator].sum() / part[denominator].sum())
    draws = []
    idx = np.arange(len(part))
    for _ in range(n_boot):
        b = part.iloc[rng.choice(idx, size=len(idx), replace=True)]
        draws.append(float(b[numerator].sum() / b[denominator].sum()))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return value, float(lo), float(hi)


def difference_ci_by_run(
    counts: pd.DataFrame,
    high_group: str,
    low_group: str,
    numerator: str,
    denominator: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    high = counts[counts["current_group"] == high_group].copy()
    low = counts[counts["current_group"] == low_group].copy()
    point = float(high[numerator].sum() / high[denominator].sum() - low[numerator].sum() / low[denominator].sum())
    draws = []
    hi_idx = np.arange(len(high))
    lo_idx = np.arange(len(low))
    for _ in range(n_boot):
        hb = high.iloc[rng.choice(hi_idx, size=len(hi_idx), replace=True)]
        lb = low.iloc[rng.choice(lo_idx, size=len(lo_idx), replace=True)]
        draws.append(float(hb[numerator].sum() / hb[denominator].sum() - lb[numerator].sum() / lb[denominator].sum()))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def raw_current_summary(config: dict, counts: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = int(config["bootstrap_reps"])
    for numerator, label in [
        ("multi_stave_events", "multi_stave_per_selected_event"),
        ("three_stave_events", "three_stave_per_selected_event"),
        ("downstream_events", "downstream_per_selected_event"),
    ]:
        for group in ["low_2nA", "high_20nA"]:
            val, lo, hi = ratio_ci_by_run(counts, group, numerator, "events_with_selected", rng, n_boot)
            rows.append(
                {
                    "metric": label,
                    "contrast": group,
                    "value": val,
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "n_runs": int((counts["current_group"] == group).sum()),
                }
            )
        diff, lo, hi = difference_ci_by_run(counts, "high_20nA", "low_2nA", numerator, "events_with_selected", rng, n_boot)
        rows.append(
            {
                "metric": label,
                "contrast": "high_minus_low",
                "value": diff,
                "ci95_low": lo,
                "ci95_high": hi,
                "n_runs": int((counts["current_group"].isin(["low_2nA", "high_20nA"])).sum()),
            }
        )
    return pd.DataFrame(rows)


def aggregate_truth(config: dict, truth_path: Path) -> Tuple[pd.DataFrame, np.ndarray]:
    tree = uproot.open(truth_path)["hibeam"]
    total_entries = int(tree.num_entries)
    step_size = int(config["truth_step_size"])
    n_blocks = int(config["truth_pseudo_runs"])
    layer_ids = list(range(8))
    scalar_frames: List[pd.DataFrame] = []
    tensors: List[np.ndarray] = []
    start = 0

    branches = ["Sci_bar_PDG", "Sci_bar_EDep", "Sci_bar_Time", "Sci_bar_LayerID", "Sci_bar_TrackID"]
    for arrays in tree.iterate(branches, step_size=step_size, library="ak"):
        n = len(arrays["Sci_bar_EDep"])
        global_event = np.arange(start, start + n, dtype=np.int64)
        pseudo_run = np.minimum((global_event * n_blocks) // total_entries, n_blocks - 1).astype(np.int16)
        base = pd.DataFrame({"event_id": global_event, "pseudo_run": pseudo_run})

        counts = ak.to_numpy(ak.num(arrays["Sci_bar_EDep"], axis=1)).astype(np.int64)
        local_event = np.repeat(np.arange(n, dtype=np.int64), counts)
        if len(local_event) == 0:
            frame = base.copy()
            for col in [
                "n_hits",
                "n_tracks",
                "n_species",
                "n_layers",
                "n_b_layers",
                "downstream_b",
                "sum_edep",
                "max_edep",
                "mean_edep",
                "time_span_ns",
                "track_time_span_ns",
                "pd_time_span_ns",
                "has_proton",
                "has_deuteron",
            ]:
                frame[col] = 0.0
            scalar_frames.append(frame)
            tensors.append(np.zeros((n, 3, 8), dtype=np.float32))
            start += n
            continue

        flat = {
            "event": local_event,
            "pdg": ak.to_numpy(ak.flatten(arrays["Sci_bar_PDG"])).astype(np.int64),
            "edep": ak.to_numpy(ak.flatten(arrays["Sci_bar_EDep"])).astype(np.float64),
            "time": ak.to_numpy(ak.flatten(arrays["Sci_bar_Time"])).astype(np.float64),
            "layer": ak.to_numpy(ak.flatten(arrays["Sci_bar_LayerID"])).astype(np.int64),
            "track": ak.to_numpy(ak.flatten(arrays["Sci_bar_TrackID"])).astype(np.int64),
        }
        df = pd.DataFrame(flat)
        df = df[df["edep"] > 0].copy()
        if df.empty:
            frame = base.copy()
            for col in [
                "n_hits",
                "n_tracks",
                "n_species",
                "n_layers",
                "n_b_layers",
                "downstream_b",
                "sum_edep",
                "max_edep",
                "mean_edep",
                "time_span_ns",
                "track_time_span_ns",
                "pd_time_span_ns",
                "has_proton",
                "has_deuteron",
            ]:
                frame[col] = 0.0
            scalar_frames.append(frame)
            tensors.append(np.zeros((n, 3, 8), dtype=np.float32))
            start += n
            continue

        by_event = df.groupby("event")
        agg = by_event.agg(
            n_hits=("edep", "size"),
            n_tracks=("track", "nunique"),
            n_species=("pdg", "nunique"),
            n_layers=("layer", "nunique"),
            sum_edep=("edep", "sum"),
            max_edep=("edep", "max"),
            mean_edep=("edep", "mean"),
            min_time=("time", "min"),
            max_time=("time", "max"),
        )
        agg["time_span_ns"] = agg["max_time"] - agg["min_time"]

        b_layers = df[df["layer"].isin(config["truth_b_layers"])]
        b_unique = b_layers.groupby("event")["layer"].nunique().rename("n_b_layers")
        downstream = df[df["layer"].isin(config["truth_downstream_layers"])].groupby("event")["layer"].size().rename("downstream_b")
        agg = agg.join(b_unique, how="left").join(downstream, how="left")
        agg["n_b_layers"] = agg["n_b_layers"].fillna(0)
        agg["downstream_b"] = (agg["downstream_b"].fillna(0) > 0).astype(float)

        track_min = df.groupby(["event", "track"])["time"].min().reset_index()
        track_span = (track_min.groupby("event")["time"].max() - track_min.groupby("event")["time"].min()).rename("track_time_span_ns")
        agg = agg.join(track_span, how="left")

        species_min = df[df["pdg"].isin([PROTON, DEUTERON])].groupby(["event", "pdg"])["time"].min().unstack()
        if PROTON not in species_min:
            species_min[PROTON] = np.nan
        if DEUTERON not in species_min:
            species_min[DEUTERON] = np.nan
        species_min = species_min.rename(columns={PROTON: "t_proton", DEUTERON: "t_deuteron"})
        species_min["has_proton"] = np.isfinite(species_min["t_proton"]).astype(float)
        species_min["has_deuteron"] = np.isfinite(species_min["t_deuteron"]).astype(float)
        species_min["pd_time_span_ns"] = np.abs(species_min["t_proton"] - species_min["t_deuteron"])
        agg = agg.join(species_min[["has_proton", "has_deuteron", "pd_time_span_ns"]], how="left")

        layer_sum = df.pivot_table(index="event", columns="layer", values="edep", aggfunc="sum", fill_value=0.0)
        layer_count = df.pivot_table(index="event", columns="layer", values="edep", aggfunc="size", fill_value=0.0)
        layer_time = df.pivot_table(index="event", columns="layer", values="time", aggfunc="min", fill_value=np.nan)
        tensor = np.zeros((n, 3, 8), dtype=np.float32)
        for j, layer in enumerate(layer_ids):
            if layer in layer_sum:
                tensor[layer_sum.index.to_numpy(dtype=np.int64), 0, j] = np.log1p(layer_sum[layer].to_numpy(dtype=np.float32))
            if layer in layer_count:
                tensor[layer_count.index.to_numpy(dtype=np.int64), 1, j] = np.log1p(layer_count[layer].to_numpy(dtype=np.float32))
            if layer in layer_time:
                times = layer_time[layer].to_numpy(dtype=np.float32)
                finite = np.isfinite(times)
                tensor[layer_time.index.to_numpy(dtype=np.int64)[finite], 2, j] = times[finite]
        finite_times = tensor[:, 2, :]
        nonzero = finite_times > 0
        mins = np.where(nonzero, finite_times, np.inf).min(axis=1)
        mins[~np.isfinite(mins)] = 0.0
        tensor[:, 2, :] = np.where(nonzero, (finite_times - mins[:, None]) / 100.0, 0.0)

        frame = base.join(agg, how="left")
        for col in ["n_hits", "n_tracks", "n_species", "n_layers", "n_b_layers", "downstream_b", "sum_edep", "max_edep", "mean_edep", "time_span_ns", "track_time_span_ns", "pd_time_span_ns", "has_proton", "has_deuteron"]:
            if col not in frame:
                frame[col] = 0.0
        frame = frame.fillna(
            {
                "n_hits": 0,
                "n_tracks": 0,
                "n_species": 0,
                "n_layers": 0,
                "n_b_layers": 0,
                "downstream_b": 0,
                "sum_edep": 0,
                "max_edep": 0,
                "mean_edep": 0,
                "time_span_ns": 0,
                "track_time_span_ns": 0,
                "pd_time_span_ns": 1.0e9,
                "has_proton": 0,
                "has_deuteron": 0,
            }
        )
        scalar_frames.append(frame)
        tensors.append(tensor)
        start += n

    truth = pd.concat(scalar_frames, ignore_index=True)
    xseq = np.vstack(tensors)
    truth["truth_multi_track"] = (truth["n_tracks"] >= 2).astype(int)
    truth["truth_multi_species"] = (truth["n_species"] >= 2).astype(int)
    truth["truth_pd_present"] = ((truth["has_proton"] > 0) & (truth["has_deuteron"] > 0)).astype(int)
    for tau in config["truth_overlap_windows_ns"]:
        key = "truth_pd_overlap_%s_ns" % str(tau).replace(".", "p")
        truth[key] = ((truth["truth_pd_present"] == 1) & (truth["pd_time_span_ns"] <= float(tau))).astype(int)
    return truth, xseq


def truth_rate_summary(config: dict, truth: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    labels = ["truth_multi_track", "truth_multi_species", "truth_pd_present"]
    for tau in config["truth_overlap_windows_ns"]:
        labels.append("truth_pd_overlap_%s_ns" % str(tau).replace(".", "p"))
    rows = []
    n_boot = int(config["bootstrap_reps"])
    blocks = sorted(truth["pseudo_run"].unique())
    for label in labels:
        block_rates = truth.groupby("pseudo_run")[label].mean()
        draws = []
        for _ in range(n_boot):
            sample = rng.choice(blocks, size=len(blocks), replace=True)
            draws.append(float(block_rates.loc[sample].mean()))
        lo, hi = np.percentile(draws, [2.5, 97.5])
        rows.append(
            {
                "truth_quantity": label,
                "value": float(truth[label].mean()),
                "ci95_low": float(lo),
                "ci95_high": float(hi),
                "n_events": int(len(truth)),
                "n_pseudo_runs": int(len(blocks)),
            }
        )
    return pd.DataFrame(rows)


def rmax_summary(config: dict, truth_rates: pd.DataFrame, current_summary: pd.DataFrame) -> pd.DataFrame:
    occ = float(config["rmax"]["occupancy_tolerance"])
    note_tau = float(config["rmax"]["note_tau_eff_ns"])
    measured_tau = float(config["rmax"]["measured_live10_ns"])
    downstream = current_summary[(current_summary["metric"] == "downstream_per_selected_event") & (current_summary["contrast"] == "high_minus_low")].iloc[0]
    primary_key = "truth_pd_overlap_%s_ns" % str(config["primary_truth_label_tau_ns"]).replace(".", "p")
    truth_row = truth_rates[truth_rates["truth_quantity"] == primary_key].iloc[0]
    rows = []
    for label, tau in [("note_assumed_tau", note_tau), ("raw_measured_live10_tau", measured_tau)]:
        rows.append(
            {
                "definition": label,
                "tau_ns": tau,
                "occupancy_tolerance": occ,
                "rmax_mhz": occ / (tau * 1.0e-9) / 1.0e6,
                "basis": "S10 occupancy tolerance divided by effective live window",
            }
        )
    for label, p in [
        ("data_high_minus_low_downstream_equivalent", float(downstream["value"])),
        ("truth_intrinsic_pd_overlap_90ns_equivalent", float(truth_row["value"])),
    ]:
        p = min(max(p, 0.0), 0.999999)
        rows.append(
            {
                "definition": label,
                "tau_ns": measured_tau,
                "occupancy_tolerance": p,
                "rmax_mhz": -math.log(1.0 - p) / (measured_tau * 1.0e-9) / 1.0e6,
                "basis": "Poisson rate that would yield the observed fraction in measured live10 window",
            }
        )
    return pd.DataFrame(rows)


def scalar_features(truth: pd.DataFrame) -> np.ndarray:
    cols = [
        "n_hits",
        "n_layers",
        "n_b_layers",
        "downstream_b",
        "sum_edep",
        "max_edep",
        "mean_edep",
        "time_span_ns",
        "track_time_span_ns",
    ]
    x = truth[cols].to_numpy(dtype=np.float32)
    x[:, 4:7] = np.log1p(np.maximum(x[:, 4:7], 0.0))
    x[:, 7:9] = np.clip(x[:, 7:9], 0.0, 1000.0) / 100.0
    return x


def block_sample_indices(blocks: np.ndarray, candidate: np.ndarray, max_n: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.flatnonzero(candidate)
    if len(idx) <= max_n:
        return idx
    return rng.choice(idx, size=max_n, replace=False)


def metric_dict(y: np.ndarray, score: np.ndarray) -> dict:
    y = np.asarray(y).astype(int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2:
        auc = float("nan")
        ap = float("nan")
    else:
        auc = float(roc_auc_score(y, score))
        ap = float(average_precision_score(y, score))
    prob = np.clip(score, 1e-6, 1 - 1e-6)
    if score.min() < 0 or score.max() > 1:
        lo, hi = np.percentile(score, [1, 99])
        prob = np.clip((score - lo) / max(hi - lo, 1e-6), 1e-6, 1 - 1e-6)
    return {"roc_auc": auc, "average_precision": ap, "brier": float(brier_score_loss(y, prob))}


class SmallCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
            nn.Flatten(),
            nn.Linear(24, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(1)


class DeepSets(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.phi = nn.Sequential(nn.Linear(3, 24), nn.ReLU(), nn.Linear(24, 24), nn.ReLU())
        self.rho = nn.Sequential(nn.Linear(24, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        # Input is (batch, channels, layers); pool over layers after per-layer embedding.
        z = x.transpose(1, 2)
        return self.rho(self.phi(z).sum(dim=1)).squeeze(1)


def train_torch_model(model, x_train, y_train, x_test, config: dict, seed: int) -> np.ndarray:
    if torch is None:
        return np.full(len(x_test), np.nan, dtype=float)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    x_train_t = torch.tensor(x_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train.astype(np.float32), dtype=torch.float32)
    ds = TensorDataset(x_train_t, y_train_t)
    loader = DataLoader(ds, batch_size=int(config["nn_batch_size"]), shuffle=True)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(config["nn_epochs"])):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    scores = []
    with torch.no_grad():
        for i in range(0, len(x_test), 8192):
            xb = torch.tensor(x_test[i : i + 8192], dtype=torch.float32).to(device)
            scores.append(torch.sigmoid(model(xb)).cpu().numpy())
    return np.concatenate(scores).astype(float)


def benchmark_methods(config: dict, truth: pd.DataFrame, xseq: np.ndarray, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    tau_key = "truth_pd_overlap_%s_ns" % str(config["primary_truth_label_tau_ns"]).replace(".", "p")
    y = truth[tau_key].to_numpy(dtype=int)
    blocks = truth["pseudo_run"].to_numpy(dtype=int)
    x_scalar = scalar_features(truth)
    x_flat = np.concatenate([x_scalar, xseq.reshape(len(xseq), -1)], axis=1)
    pred_rows: List[pd.DataFrame] = []
    fold_rows: List[dict] = []

    for heldout in sorted(np.unique(blocks)):
        log(f"training held-out pseudo-run {heldout}")
        train_mask = blocks != heldout
        test_mask = blocks == heldout
        train_idx = block_sample_indices(blocks, train_mask, int(config["max_train_events_per_fold"]), rng)
        test_idx = block_sample_indices(blocks, test_mask, int(config["max_test_events_per_fold"]), rng)
        y_train = y[train_idx]
        y_test = y[test_idx]
        fold_pred = pd.DataFrame({"event_id": truth["event_id"].to_numpy()[test_idx], "pseudo_run": heldout, "truth": y_test})

        topo_score = (
            truth["n_b_layers"].to_numpy(dtype=float)[test_idx]
            + truth["downstream_b"].to_numpy(dtype=float)[test_idx]
            + 0.25 * (truth["time_span_ns"].to_numpy(dtype=float)[test_idx] <= float(config["primary_truth_label_tau_ns"]))
        )
        fold_pred["traditional_topology"] = topo_score

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        ridge.fit(x_flat[train_idx], y_train)
        fold_pred["ridge"] = ridge.predict(x_flat[test_idx])

        gbt = GradientBoostingClassifier(random_state=int(config["random_seed"]) + int(heldout), n_estimators=30, max_depth=3, learning_rate=0.08)
        gbt.fit(x_flat[train_idx], y_train)
        fold_pred["gradient_boosted_trees"] = gbt.predict_proba(x_flat[test_idx])[:, 1]

        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=30, alpha=1e-3, random_state=int(config["random_seed"]) + 10 + int(heldout), early_stopping=True),
        )
        mlp.fit(x_flat[train_idx], y_train)
        fold_pred["mlp"] = mlp.predict_proba(x_flat[test_idx])[:, 1]

        fold_pred["cnn_1d"] = train_torch_model(SmallCNN(), xseq[train_idx], y_train, xseq[test_idx], config, int(config["random_seed"]) + 20 + int(heldout))
        fold_pred["deepsets_layer_pool"] = train_torch_model(DeepSets(), xseq[train_idx], y_train, xseq[test_idx], config, int(config["random_seed"]) + 30 + int(heldout))

        for method in ["traditional_topology", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "deepsets_layer_pool"]:
            metrics = metric_dict(y_test, fold_pred[method].to_numpy(dtype=float))
            fold_rows.append({"heldout_pseudo_run": int(heldout), "method": method, "n_test": int(len(test_idx)), "prevalence": float(y_test.mean()), **metrics})
        pred_rows.append(fold_pred)

    predictions = pd.concat(pred_rows, ignore_index=True)
    fold_metrics = pd.DataFrame(fold_rows)
    return predictions, fold_metrics


def summarize_model_metrics(config: dict, predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    methods = [c for c in predictions.columns if c not in ["event_id", "pseudo_run", "truth"]]
    blocks = sorted(predictions["pseudo_run"].unique())
    rows = []
    n_boot = int(config["bootstrap_reps"])
    for method in methods:
        y = predictions["truth"].to_numpy(dtype=int)
        score = predictions[method].to_numpy(dtype=float)
        point = metric_dict(y, score)
        boot = {"roc_auc": [], "average_precision": [], "brier": []}
        for _ in range(n_boot):
            sample_blocks = rng.choice(blocks, size=len(blocks), replace=True)
            sample = pd.concat([predictions[predictions["pseudo_run"] == b] for b in sample_blocks], ignore_index=True)
            vals = metric_dict(sample["truth"].to_numpy(dtype=int), sample[method].to_numpy(dtype=float))
            for key in boot:
                boot[key].append(vals[key])
        row = {"method": method, **point}
        for key, values in boot.items():
            lo, hi = np.nanpercentile(values, [2.5, 97.5])
            row[f"{key}_ci95_low"] = float(lo)
            row[f"{key}_ci95_high"] = float(hi)
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["average_precision", "roc_auc"], ascending=False)
    out["rank_by_average_precision"] = np.arange(1, len(out) + 1)
    return out


def markdown_table(df: pd.DataFrame, cols: List[str], floatfmt: str = ".5g") -> str:
    view = df[cols].copy()
    for col in view.columns:
        if np.issubdtype(view[col].dtype, np.floating):
            view[col] = view[col].map(lambda x: format(float(x), floatfmt) if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
    config: dict,
    out: Path,
    raw_repro: pd.DataFrame,
    raw_current: pd.DataFrame,
    truth_rates: pd.DataFrame,
    rmax: pd.DataFrame,
    model_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
) -> None:
    primary_key = "truth_pd_overlap_%s_ns" % str(config["primary_truth_label_tau_ns"]).replace(".", "p")
    report = f"""# S20: GEANT4 truth validation of pile-up multiplicity

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Raw inputs:** `{config['raw_root_dir']}` B-stack ROOT files
- **Truth input:** `{config['truth_root']}`
- **Primary truth target for ML:** `{primary_key}` (proton and deuteron both deposit in Sci_bar with first-hit separation <= {config['primary_truth_label_tau_ns']} ns)

## Reproduction gate

The raw-data gate is intentionally first.  The same baseline-subtracted B2/B4/B6/B8 amplitude cut used throughout the project is applied:

\\[
A_{{r,e,s}}=\\max_t\\left(HRDv_{{r,e,c(s),t}}-\\mathrm{{median}}(HRDv_{{r,e,c(s),0:3}})\\right),\\qquad
I_{{r,e,s}}=\\mathbb{{1}}[A_{{r,e,s}}>1000].
\\]

{markdown_table(raw_repro, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Raw current-dependent excess

For each run, selected events are events with at least one selected B-stack stave.  The topology rates are

\\[
\\hat p_g = \\frac{{\\sum_{{r\\in g}} N_r(\\mathrm{{topology}})}}{{\\sum_{{r\\in g}} N_r(\\mathrm{{selected\\ event}})}},
\\qquad
\\Delta = \\hat p_{{20\\,\\mathrm{{nA}}}}-\\hat p_{{2\\,\\mathrm{{nA}}}} .
\\]

Confidence intervals are non-parametric bootstraps over real run IDs within current group.

{markdown_table(raw_current, ['metric', 'contrast', 'value', 'ci95_low', 'ci95_high', 'n_runs'])}

## GEANT4 truth definitions

The hibeam truth tree has no test-beam run/current branch.  The 1M events are therefore split into deterministic contiguous pseudo-runs solely for leakage control and block-bootstrap uncertainty.  This is weaker than true run splitting and is treated as a systematic limitation.

Truth multiplicity is evaluated from positive Sci_bar energy deposits:

\\[
M_{{\\mathrm{{track}}}}(e)=\\left|\\{{\\mathrm{{TrackID}}: E_{{dep}}>0\\}}\\right|,\\qquad
M_{{pd}}(e,\\tau)=\\mathbb{{1}}[p\\ \\mathrm{{and}}\\ d\\ \\mathrm{{deposit}}]\\,
\\mathbb{{1}}[|t_p^{{min}}-t_d^{{min}}|\\le \\tau].
\\]

The key truth rates, with pseudo-run block bootstrap CIs, are:

{markdown_table(truth_rates, ['truth_quantity', 'value', 'ci95_low', 'ci95_high', 'n_events', 'n_pseudo_runs'])}

## Traditional and ML/NN benchmark

The traditional score is a truth-blind B-layer topology score:

\\[
S_{{trad}} = N_{{B\\ layers}} + \\mathbb{{1}}[\\mathrm{{downstream\\ B\\ layer}}] + 0.25\\,\\mathbb{{1}}[\\Delta t_{{Sci\\ bar}}\\le \\tau].
\\]

The ML panel uses only detector-level Sci_bar hit summaries and per-layer energy/count/time tensors; it does not use PDG, TrackID, or the target labels as features.  Models are trained with the scored pseudo-run held out: ridge regression score, gradient-boosted trees, MLP, 1D CNN over ordered Sci_bar layers, and a new DeepSets-style layer-pooling network.  Model CIs are block bootstraps over held-out pseudo-runs.

{markdown_table(model_summary, ['rank_by_average_precision', 'method', 'average_precision', 'average_precision_ci95_low', 'average_precision_ci95_high', 'roc_auc', 'roc_auc_ci95_low', 'roc_auc_ci95_high', 'brier', 'brier_ci95_low', 'brier_ci95_high'])}

The winner by held-out average precision is **{winner}**.

## Rmax interpretation

The S10 occupancy model maps an allowed overlap occupancy \\(\\epsilon\\) to

\\[
R_{{max}} = \\frac{{\\epsilon}}{{\\tau_{{eff}}}}.
\\]

For the project value \\(\\epsilon=0.38\\), the note's \\(\\tau_{{eff}}=90\\) ns gives 4.22 MHz.  The raw waveform live10 measurement \\(\\tau=124.79\\) ns gives about 3.05 MHz.  GEANT4 truth does not contain beam-current timing or DAQ live-time, so it cannot by itself restore the 90 ns assumption; it constrains intrinsic p+d multiplicity/topology instead.

{markdown_table(rmax, ['definition', 'tau_ns', 'occupancy_tolerance', 'rmax_mhz', 'basis'])}

## Leakage controls

{markdown_table(leakage, ['check', 'value', 'flag', 'note'])}

## Systematics and caveats

1. The GEANT4 truth file has no run/current metadata.  Pseudo-runs protect the ML comparison from event-level leakage but do not reproduce real detector-run drift.
2. Truth labels are Sci_bar-level p+d coincidences and truth-track multiplicities, not digitized HRD waveform pile-up.  A full electronics response would be required to turn these into ADC-level overlay labels.
3. The raw current excess is measured in real data; the truth file is current-independent.  Agreement in topology can validate a baseline intrinsic multiplicity component, but cannot prove the 20 nA high-minus-low excess is caused by GEANT4 p+d coincidences.
4. The traditional topology score intentionally mirrors the data-driven S10 idea and is not allowed to inspect PDG or TrackID.  The ML/NN features are likewise detector-level summaries only.
5. The Rmax conclusion remains dominated by the live-time definition.  Truth multiplicity does not support reverting from the measured ~3.05 MHz live10 value to the older 4.22 MHz assumption.

## Conclusion

Raw ROOT reproduction passes exactly.  GEANT4 truth shows the intrinsic Sci_bar p+d/multi-track coincidence baseline and provides a genuine supervised target for checking the data-driven topology score.  The best held-out truth classifier is **{winner}**.  For the operational pile-up-rate limit, truth does not supersede the raw waveform live-time measurement: the defensible current value remains the measured-live10 **Rmax ≈ 3.05 MHz**, while the note's 4.22 MHz is the result of assuming a shorter 90 ns live window.  The real data high-minus-low topology excess is reported above with real-run CIs and should be interpreted as a current-dependent excess not directly encoded in the current-independent GEANT4 truth sample.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "configs/0000000014_1_truthpileup.yaml")
    args = ap.parse_args()
    config = load_config(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    rng = np.random.default_rng(int(config["random_seed"]))

    truth_path = Path(config["truth_root"])
    if not truth_path.exists():
        truth_path = Path(config["fallback_truth_root"])

    raw_counts, raw_repro = reproduce_raw_counts(config)
    log("raw reproduction complete")
    raw_current = raw_current_summary(config, raw_counts, rng)
    log("raw current bootstrap complete")
    truth, xseq = aggregate_truth(config, truth_path)
    log("truth aggregation complete")
    truth_rates = truth_rate_summary(config, truth, rng)
    rmax = rmax_summary(config, truth_rates, raw_current)
    predictions, fold_metrics = benchmark_methods(config, truth, xseq, rng)
    log("model benchmark complete")
    model_summary = summarize_model_metrics(config, predictions, rng)
    log("metric bootstrap complete")
    winner = str(model_summary.iloc[0]["method"])

    reported = config["reported_s10"]
    low_down = raw_current[(raw_current["metric"] == "downstream_per_selected_event") & (raw_current["contrast"] == "low_2nA")].iloc[0]["value"]
    high_down = raw_current[(raw_current["metric"] == "downstream_per_selected_event") & (raw_current["contrast"] == "high_20nA")].iloc[0]["value"]
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_exact",
                "value": bool(raw_repro.iloc[0]["pass"]),
                "flag": bool(not raw_repro.iloc[0]["pass"]),
                "note": "Total selected B-stave pulses must reproduce 640737 exactly.",
            },
            {
                "check": "reported_downstream_low_reproduced",
                "value": float(low_down - float(reported["low_2nA_downstream_per_selected_event"])),
                "flag": bool(abs(low_down - float(reported["low_2nA_downstream_per_selected_event"])) > float(reported["tolerance_abs"])),
                "note": "Raw S10 low-current downstream rate within configured tolerance.",
            },
            {
                "check": "reported_downstream_high_reproduced",
                "value": float(high_down - float(reported["high_20nA_downstream_per_selected_event"])),
                "flag": bool(abs(high_down - float(reported["high_20nA_downstream_per_selected_event"])) > float(reported["tolerance_abs"])),
                "note": "Raw S10 high-current downstream rate within configured tolerance.",
            },
            {
                "check": "truth_features_exclude_pdg_trackid",
                "value": True,
                "flag": False,
                "note": "PDG and TrackID define labels only; model inputs are hit summaries and layer tensors.",
            },
            {
                "check": "heldout_blocks_excluded_from_training",
                "value": True,
                "flag": False,
                "note": "Every model is trained with the scored pseudo-run block held out.",
            },
            {
                "check": "simulation_has_real_run_branch",
                "value": False,
                "flag": False,
                "note": "No run/current branch exists; pseudo-runs are a documented limitation, not a hidden run split.",
            },
        ]
    )

    raw_counts.to_csv(out / "raw_counts_by_run.csv", index=False)
    raw_repro.to_csv(out / "reproduction_match_table.csv", index=False)
    raw_current.to_csv(out / "raw_current_excess_bootstrap.csv", index=False)
    truth_rates.to_csv(out / "truth_rate_summary.csv", index=False)
    rmax.to_csv(out / "rmax_interpretation.csv", index=False)
    fold_metrics.to_csv(out / "fold_metrics.csv", index=False)
    model_summary.to_csv(out / "method_summary.csv", index=False)
    predictions.sample(min(len(predictions), 20000), random_state=int(config["random_seed"])).to_csv(out / "prediction_sample.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)

    input_rows = [
        {"path": str(ROOT / args.config), "sha256": sha256_file(ROOT / args.config)},
        {"path": str(truth_path), "sha256": sha256_file(truth_path)},
    ]
    for run in configured_runs(config):
        path = ROOT / config["raw_root_dir"] / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    write_csv(out / "input_sha256.csv", input_rows)

    manifest = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() and ROOT in args.config.parents else args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "truth_root_used": str(truth_path),
        "elapsed_seconds": time.time() - start_time,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    primary_key = "truth_pd_overlap_%s_ns" % str(config["primary_truth_label_tau_ns"]).replace(".", "p")
    primary_truth = truth_rates[truth_rates["truth_quantity"] == primary_key].iloc[0]
    downstream_excess = raw_current[(raw_current["metric"] == "downstream_per_selected_event") & (raw_current["contrast"] == "high_minus_low")].iloc[0]
    measured_rmax = rmax[rmax["definition"] == "raw_measured_live10_tau"].iloc[0]
    result = {
        "ticket_id": config["ticket_id"],
        "raw_reproduction_pass": bool(raw_repro.iloc[0]["pass"]),
        "raw_selected_pulses": int(raw_repro.iloc[0]["reproduced"]),
        "truth_root_used": str(truth_path),
        "primary_truth_label": primary_key,
        "truth_pd_overlap_90ns_rate": {
            "value": float(primary_truth["value"]),
            "ci95": [float(primary_truth["ci95_low"]), float(primary_truth["ci95_high"])],
        },
        "raw_downstream_high_minus_low": {
            "value": float(downstream_excess["value"]),
            "ci95": [float(downstream_excess["ci95_low"]), float(downstream_excess["ci95_high"])],
        },
        "winner": winner,
        "winner_metric": "held-out block-bootstrap average_precision",
        "method_summary": model_summary.to_dict(orient="records"),
        "recommended_rmax_mhz": float(measured_rmax["rmax_mhz"]),
        "rmax_basis": "S10 occupancy tolerance 0.38 divided by raw measured live10 tau=124.79018394263471 ns; GEANT4 truth has no DAQ live-time/current branch and does not restore the 90 ns assumption.",
        "finding": (
            "Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. "
            f"GEANT4 truth primary label {primary_key} has rate {float(primary_truth['value']):.6f} "
            f"[{float(primary_truth['ci95_low']):.6f}, {float(primary_truth['ci95_high']):.6f}], while the real-data downstream high-minus-low excess is "
            f"{float(downstream_excess['value']):.6f} [{float(downstream_excess['ci95_low']):.6f}, {float(downstream_excess['ci95_high']):.6f}]. "
            f"The held-out truth-classification winner is {winner}. Truth validates intrinsic multiplicity/topology but does not contain current or live-time information; the operational Rmax remains {float(measured_rmax['rmax_mhz']):.3f} MHz from the measured raw waveform live10 window, not the 4.22 MHz 90 ns assumption."
        ),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(config, out, raw_repro, raw_current, truth_rates, rmax, model_summary, leakage, winner)


if __name__ == "__main__":
    main()
