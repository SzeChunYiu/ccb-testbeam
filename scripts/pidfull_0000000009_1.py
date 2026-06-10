#!/usr/bin/env python3
"""Ticket 0000000009.1.pidfull: GEANT4-truth PID on B-stack scintillator patterns."""

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
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - recorded in manifest if unavailable.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

if torch is not None:
    torch.set_num_threads(2)


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    return obj


def raw_runs(raw_dir: Path) -> List[int]:
    runs = []
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        try:
            runs.append(int(path.stem.split("_run_")[1]))
        except Exception:
            continue
    return [run for run in runs if 12 <= run <= 65]


def configured_raw_runs(config: dict) -> List[int]:
    if "raw_run_groups" not in config:
        return raw_runs(ROOT / config["raw_root_dir"])
    runs: List[int] = []
    for values in config["raw_run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def reproduce_raw_counts(config: dict) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    raw_dir = ROOT / config["raw_root_dir"]
    channels = np.asarray(list(config["raw_b_channels"].values()), dtype=int)
    stave_names = list(config["raw_b_channels"].keys())
    baseline_idx = np.asarray(config["raw_baseline_samples"], dtype=int)
    nsamp = int(config["raw_samples_per_channel"])
    cut = float(config["raw_amplitude_cut_adc"])
    rows = []
    inputs = []
    totals = {name: 0 for name in stave_names}
    total_selected = 0
    total_events = 0

    for run in configured_raw_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        inputs.append({"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
        run_counts = {name: 0 for name in stave_names}
        events = 0
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            b_wave = wave[:, channels, :]
            corrected = b_wave - np.median(b_wave[:, :, baseline_idx], axis=2)[:, :, None]
            selected = corrected.max(axis=2) > cut
            events += int(selected.shape[0])
            for idx, name in enumerate(stave_names):
                run_counts[name] += int(selected[:, idx].sum())
        run_total = int(sum(run_counts.values()))
        total_selected += run_total
        total_events += events
        for name in stave_names:
            totals[name] += run_counts[name]
        rows.append({"run": run, "events": events, "selected_pulses": run_total, **run_counts})

    frame = pd.DataFrame(rows)
    summary = {
        "raw_root_dir": config["raw_root_dir"],
        "runs": len(frame),
        "events": int(total_events),
        "selected_pulses": int(total_selected),
        "expected_selected_pulses": int(config["raw_expected_selected_pulses"]),
        "delta": int(total_selected - int(config["raw_expected_selected_pulses"])),
        "passed": int(total_selected) == int(config["raw_expected_selected_pulses"]),
        "stave_counts": {k: int(v) for k, v in totals.items()},
    }
    if not summary["passed"]:
        raise RuntimeError(f"raw ROOT reproduction failed: {summary}")
    return frame, summary, pd.DataFrame(inputs)


def choose_geant4_path(config: dict) -> Path:
    primary = Path(config["geant4_root"])
    if primary.exists():
        return primary
    fallback = Path(config["fallback_geant4_root"])
    if fallback.exists():
        return fallback
    raise FileNotFoundError(primary)


def weighted_mean(numer: np.ndarray, denom: np.ndarray) -> np.ndarray:
    out = np.zeros_like(numer, dtype=np.float32)
    np.divide(numer, denom, out=out, where=denom > 0)
    return out


def extract_geant4_features(config: dict, geant4_path: Path) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, List[str]]:
    tree = uproot.open(geant4_path)["hibeam"]
    classes = list(config["classes"].keys())
    pdgs = np.asarray([int(config["classes"][name]) for name in classes], dtype=np.int64)
    n_layers = int(config["sim_layers"])
    b_id = int(config["sim_b_stack_layer_id1"])
    n_blocks = int(config["sim_run_blocks"])
    dom_min = float(config["dominant_truth_fraction_min"])
    min_edep = float(config["min_b_edep"])

    meta_parts = []
    seq_parts = []
    tab_parts = []
    entry0 = 0
    branches = [
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_TrackLength",
        "Sci_bar_Position_X",
        "Sci_bar_Position_Y",
        "Sci_bar_Position_Z",
    ]
    for ibatch, batch in enumerate(tree.iterate(branches, step_size=100000, library="ak"), start=1):
        n = len(batch["Sci_bar_PDG"])
        layer = batch["Sci_bar_LayerID"]
        layer1 = batch["Sci_bar_LayerID1"]
        pdg = batch["Sci_bar_PDG"]
        edep = batch["Sci_bar_EDep"]
        time_arr = batch["Sci_bar_Time"]
        trk = batch["Sci_bar_TrackLength"]
        x = batch["Sci_bar_Position_X"]
        y = batch["Sci_bar_Position_Y"]
        z = batch["Sci_bar_Position_Z"]
        b_mask = layer1 == b_id
        total_e = np.asarray(ak.sum(ak.where(b_mask, edep, 0.0), axis=1), dtype=np.float32)
        class_e = np.vstack(
            [np.asarray(ak.sum(ak.where(b_mask & (pdg == int(code)), edep, 0.0), axis=1), dtype=np.float32) for code in pdgs]
        ).T
        target_max = class_e.max(axis=1)
        y_idx = class_e.argmax(axis=1).astype(np.int64)
        keep = (total_e > min_edep) & (target_max / np.maximum(total_e, min_edep) >= dom_min)
        if not np.any(keep):
            entry0 += n
            continue

        e_layers = []
        count_layers = []
        time_layers = []
        path_layers = []
        for li in range(n_layers):
            m = b_mask & (layer == li)
            e = np.asarray(ak.sum(ak.where(m, edep, 0.0), axis=1), dtype=np.float32)
            c = np.asarray(ak.sum(ak.where(m, 1, 0), axis=1), dtype=np.float32)
            te = np.asarray(ak.sum(ak.where(m, edep * time_arr, 0.0), axis=1), dtype=np.float32)
            le = np.asarray(ak.sum(ak.where(m, trk, 0.0), axis=1), dtype=np.float32)
            e_layers.append(e)
            count_layers.append(c)
            time_layers.append(weighted_mean(te, e))
            path_layers.append(le)
        e_layers = np.vstack(e_layers).T.astype(np.float32)
        count_layers = np.vstack(count_layers).T.astype(np.float32)
        time_layers = np.vstack(time_layers).T.astype(np.float32)
        path_layers = np.vstack(path_layers).T.astype(np.float32)
        frac = e_layers / np.maximum(total_e[:, None], min_edep)
        layer_axis = np.arange(n_layers, dtype=np.float32)
        centroid = (frac * layer_axis[None, :]).sum(axis=1)
        spread = np.sqrt(np.maximum((frac * (layer_axis[None, :] - centroid[:, None]) ** 2).sum(axis=1), 0.0))
        first_e = e_layers[:, :2].sum(axis=1)
        tail_e = e_layers[:, -3:].sum(axis=1)
        max_frac = frac.max(axis=1)
        active_layers = (e_layers > 0).sum(axis=1)
        weighted_t = (time_layers * e_layers).sum(axis=1) / np.maximum(total_e, min_edep)
        t_spread = np.sqrt(np.maximum((frac * (time_layers - weighted_t[:, None]) ** 2).sum(axis=1), 0.0))
        total_path = path_layers.sum(axis=1)
        mean_dedx = total_e / np.maximum(total_path, min_edep)
        wx = weighted_mean(np.asarray(ak.sum(ak.where(b_mask, edep * x, 0.0), axis=1), dtype=np.float32), total_e)
        wy = weighted_mean(np.asarray(ak.sum(ak.where(b_mask, edep * y, 0.0), axis=1), dtype=np.float32), total_e)
        wz = weighted_mean(np.asarray(ak.sum(ak.where(b_mask, edep * z, 0.0), axis=1), dtype=np.float32), total_e)

        seq = np.stack([np.log1p(e_layers), frac, time_layers / 100.0], axis=1).astype(np.float32)
        tab = np.column_stack(
            [
                np.log1p(e_layers),
                frac,
                np.log1p(total_e),
                np.log1p(first_e),
                np.log1p(tail_e),
                tail_e / np.maximum(first_e, min_edep),
                centroid,
                spread,
                max_frac,
                active_layers,
                weighted_t,
                t_spread,
                np.log1p(total_path),
                np.log1p(mean_dedx),
                wx,
                wy,
                wz,
            ]
        ).astype(np.float32)
        event_id = np.arange(entry0, entry0 + n, dtype=np.int64)
        sim_run = np.floor(event_id.astype(np.float64) * n_blocks / float(tree.num_entries)).astype(int)
        sim_run = np.clip(sim_run, 0, n_blocks - 1)
        meta = pd.DataFrame(
            {
                "event_index": event_id,
                "sim_run": sim_run,
                "truth_class": np.asarray(classes, dtype=object)[y_idx],
                "truth_pdg": pdgs[y_idx],
                "dominant_fraction": target_max / np.maximum(total_e, min_edep),
                "b_total_edep": total_e,
                "b_active_layers": active_layers,
            }
        )
        meta_parts.append(meta.loc[keep].reset_index(drop=True))
        seq_parts.append(seq[keep])
        tab_parts.append(tab[keep])
        print(f"geant4 batch {ibatch}: kept {int(keep.sum())} labeled B-stack events", flush=True)
        entry0 += n

    meta = pd.concat(meta_parts, ignore_index=True)
    seq = np.concatenate(seq_parts, axis=0)
    tab = np.vstack(tab_parts)
    return meta, seq, tab, classes


def balanced_subsample(meta: pd.DataFrame, seq: np.ndarray, tab: np.ndarray, classes: List[str], config: dict):
    rng = np.random.default_rng(int(config["random_seed"]))
    max_per_class = int(config["max_per_class"])
    chosen = []
    for cls in classes:
        idx = np.flatnonzero(meta["truth_class"].to_numpy() == cls)
        if len(idx) > max_per_class:
            idx = rng.choice(idx, size=max_per_class, replace=False)
        chosen.append(idx)
    idx = np.concatenate(chosen)
    rng.shuffle(idx)
    return meta.iloc[idx].reset_index(drop=True), seq[idx], tab[idx]


def class_weights(y: np.ndarray, n_classes: int) -> np.ndarray:
    counts = np.bincount(y, minlength=n_classes).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    return weights / weights.mean()


def traditional_fit_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, n_classes: int) -> np.ndarray:
    # Handcrafted dE/dx band classifier: robust diagonal Mahalanobis bands in charge-shape space.
    use_cols = list(range(16, x_train.shape[1]))
    xt = x_train[:, use_cols]
    xv = x_test[:, use_cols]
    med = np.zeros((n_classes, len(use_cols)), dtype=np.float32)
    scale = np.ones_like(med)
    prior = np.zeros(n_classes, dtype=np.float32)
    for c in range(n_classes):
        rows = xt[y_train == c]
        prior[c] = max(len(rows), 1)
        med[c] = np.median(rows, axis=0)
        q25 = np.percentile(rows, 25, axis=0)
        q75 = np.percentile(rows, 75, axis=0)
        scale[c] = np.maximum((q75 - q25) / 1.349, 1e-3)
    prior = np.log(prior / prior.sum())
    score = np.empty((len(xv), n_classes), dtype=np.float32)
    for c in range(n_classes):
        z = (xv - med[c]) / scale[c]
        score[:, c] = -0.5 * np.sum(z * z, axis=1) + prior[c]
    return score.argmax(axis=1)


class SmallCNN(nn.Module):
    def __init__(self, n_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(3, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(32, n_classes),
        )

    def forward(self, seq, tab=None):
        return self.net(seq)


class HybridCNN(nn.Module):
    def __init__(self, n_tab: int, n_classes: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(3, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(32 + n_tab, 64), nn.ReLU(), nn.Dropout(0.05), nn.Linear(64, n_classes))

    def forward(self, seq, tab=None):
        return self.head(torch.cat([self.conv(seq), tab], dim=1))


def torch_predict(model_cls, seq_train, tab_train, y_train, seq_test, tab_test, config, n_classes, use_tab: bool) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(int(config["random_seed"]))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    scaler_mean = tab_train.mean(axis=0, keepdims=True)
    scaler_std = tab_train.std(axis=0, keepdims=True) + 1e-6
    tab_train_s = (tab_train - scaler_mean) / scaler_std
    tab_test_s = (tab_test - scaler_mean) / scaler_std
    model = model_cls(tab_train.shape[1], n_classes).to(device) if use_tab else model_cls(n_classes).to(device)
    weights = torch.tensor(class_weights(y_train, n_classes), dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-3)
    ds = TensorDataset(
        torch.tensor(seq_train, dtype=torch.float32),
        torch.tensor(tab_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long),
    )
    loader = DataLoader(ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["torch_epochs"])):
        for sb, tb, yb in loader:
            sb = sb.to(device)
            tb = tb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(sb, tb if use_tab else None), yb)
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(seq_test), 2048):
            sb = torch.tensor(seq_test[start : start + 2048], dtype=torch.float32, device=device)
            tb = torch.tensor(tab_test_s[start : start + 2048], dtype=torch.float32, device=device)
            preds.append(model(sb, tb if use_tab else None).argmax(dim=1).cpu().numpy())
    return np.concatenate(preds)


def run_benchmarks(meta: pd.DataFrame, seq: np.ndarray, tab: np.ndarray, classes: List[str], config: dict):
    y = pd.Categorical(meta["truth_class"], categories=classes).codes.astype(np.int64)
    groups = meta["sim_run"].to_numpy(dtype=int)
    n_classes = len(classes)
    methods = ["traditional_bands", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "hybrid_cnn_tabular"]
    preds = {name: np.full(len(y), -1, dtype=np.int64) for name in methods}
    fold_rows = []
    for group in sorted(np.unique(groups)):
        print(f"benchmark fold sim_run={int(group)} train={int((groups != group).sum())} test={int((groups == group).sum())}", flush=True)
        test = groups == group
        train = ~test
        x_train, x_test = tab[train], tab[test]
        y_train, y_test = y[train], y[test]
        seq_train, seq_test = seq[train], seq[test]
        preds["traditional_bands"][test] = traditional_fit_predict(x_train, y_train, x_test, n_classes)
        ridge = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=500, multi_class="auto"))
        ridge.fit(x_train, y_train)
        preds["ridge"][test] = ridge.predict(x_test)
        hgb = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.08, l2_regularization=0.05, random_state=int(config["random_seed"]))
        hgb.fit(x_train, y_train, sample_weight=class_weights(y_train, n_classes)[y_train])
        preds["gradient_boosted_trees"][test] = hgb.predict(x_test)
        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, batch_size=256, max_iter=60, early_stopping=True, random_state=int(config["random_seed"])),
        )
        mlp.fit(x_train, y_train)
        preds["mlp"][test] = mlp.predict(x_test)
        preds["cnn1d"][test] = torch_predict(SmallCNN, seq_train, x_train, y_train, seq_test, x_test, config, n_classes, use_tab=False)
        preds["hybrid_cnn_tabular"][test] = torch_predict(HybridCNN, seq_train, x_train, y_train, seq_test, x_test, config, n_classes, use_tab=True)
        for method in methods:
            fold_rows.append({"sim_run": int(group), "method": method, "n": int(test.sum()), "balanced_accuracy": float(balanced_accuracy_score(y_test, preds[method][test]))})
    return preds, pd.DataFrame(fold_rows), y


def metric_bundle(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def summarize_metrics(y: np.ndarray, groups: np.ndarray, preds: Dict[str, np.ndarray], classes: List[str], config: dict):
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    reps = int(config["bootstrap_reps"])
    unique_groups = np.unique(groups)
    metric_rows = []
    species_rows = []
    for method, pred in preds.items():
        base = metric_bundle(y, pred)
        boot = {key: [] for key in base}
        for _ in range(reps):
            sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
            idx = np.concatenate([np.flatnonzero(groups == g) for g in sampled])
            mb = metric_bundle(y[idx], pred[idx])
            for key, val in mb.items():
                boot[key].append(val)
        row = {"method": method, "n": int(len(y)), **base}
        for key, vals in boot.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        metric_rows.append(row)
        for ci, cls in enumerate(classes):
            truth = y == ci
            pred_c = pred == ci
            tp = int(np.sum(truth & pred_c))
            fp = int(np.sum(~truth & pred_c))
            fn = int(np.sum(truth & ~pred_c))
            pur = tp / max(tp + fp, 1)
            eff = tp / max(tp + fn, 1)
            pur_b, eff_b = [], []
            for _ in range(reps):
                sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
                idx = np.concatenate([np.flatnonzero(groups == g) for g in sampled])
                t = y[idx] == ci
                p = pred[idx] == ci
                btp = int(np.sum(t & p))
                bfp = int(np.sum(~t & p))
                bfn = int(np.sum(t & ~p))
                pur_b.append(btp / max(btp + bfp, 1))
                eff_b.append(btp / max(btp + bfn, 1))
            species_rows.append(
                {
                    "method": method,
                    "species": cls,
                    "truth_n": int(truth.sum()),
                    "pred_n": int(pred_c.sum()),
                    "purity": float(pur),
                    "purity_ci_low": float(np.percentile(pur_b, 2.5)),
                    "purity_ci_high": float(np.percentile(pur_b, 97.5)),
                    "efficiency": float(eff),
                    "efficiency_ci_low": float(np.percentile(eff_b, 2.5)),
                    "efficiency_ci_high": float(np.percentile(eff_b, 97.5)),
                }
            )
    return pd.DataFrame(metric_rows).sort_values("balanced_accuracy", ascending=False), pd.DataFrame(species_rows)


def leakage_checks(meta: pd.DataFrame, tab: np.ndarray, y: np.ndarray, config: dict) -> pd.DataFrame:
    rows = []
    groups = meta["sim_run"].to_numpy(dtype=int)
    # Identifier-only model must not learn species if the block split is meaningful.
    x_id = meta[["event_index", "sim_run"]].to_numpy(dtype=np.float32)
    pred = np.full(len(y), -1, dtype=np.int64)
    for group in sorted(np.unique(groups)):
        train = groups != group
        test = groups == group
        model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=300))
        model.fit(x_id[train], y[train])
        pred[test] = model.predict(x_id[test])
    rows.append({"check": "identifier_only_group_heldout_balanced_accuracy", "value": float(balanced_accuracy_score(y, pred)), "threshold": 0.45, "pass": bool(balanced_accuracy_score(y, pred) < 0.45)})
    # Shuffled labels through ridge should be near chance.
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    y_shuf = y.copy()
    rng.shuffle(y_shuf)
    pred = np.full(len(y), -1, dtype=np.int64)
    for group in sorted(np.unique(groups)):
        train = groups != group
        test = groups == group
        model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=300))
        model.fit(tab[train], y_shuf[train])
        pred[test] = model.predict(tab[test])
    rows.append({"check": "shuffled_label_ridge_balanced_accuracy", "value": float(balanced_accuracy_score(y_shuf, pred)), "threshold": 0.40, "pass": bool(balanced_accuracy_score(y_shuf, pred) < 0.40)})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: List[str], floatfmt: str = ".4f") -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda v: format(v, floatfmt))
    labels = [str(c) for c in view.columns]
    rows = [[str(v) for v in row] for row in view.to_numpy()]
    widths = [len(label) for label in labels]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))
    def fmt(row):
        return "| " + " | ".join(value.ljust(widths[i]) for i, value in enumerate(row)) + " |"
    return "\n".join([fmt(labels), "| " + " | ".join("-" * w for w in widths) + " |"] + [fmt(row) for row in rows])


def write_report(out: Path, config: dict, raw_summary: dict, class_counts: pd.DataFrame, metrics: pd.DataFrame, species: pd.DataFrame, fold: pd.DataFrame, leakage: pd.DataFrame, winner: str, geant4_path: Path):
    winner_row = metrics.loc[metrics["method"] == winner].iloc[0]
    lines = [
        "# Study report: PID-full GEANT4-truth B-stave particle ID",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Raw reproduction input:** `{config['raw_root_dir']}`",
        f"- **GEANT4 truth input:** `{geant4_path}`",
        "",
        "## Executive result",
        "",
        (
            f"The winner is **{winner}** with run-block held-out balanced accuracy "
            f"{winner_row['balanced_accuracy']:.4f} "
            f"[{winner_row['balanced_accuracy_ci_low']:.4f}, {winner_row['balanced_accuracy_ci_high']:.4f}] "
            f"and macro-F1 {winner_row['macro_f1']:.4f} "
            f"[{winner_row['macro_f1_ci_low']:.4f}, {winner_row['macro_f1_ci_high']:.4f}]."
        ),
        "",
        "The labels are not inferred from test-beam data. They are GEANT4 hit-truth labels: for every simulated event, Sci_bar hits with `LayerID1 == 2` are treated as the B-stack, hit energy deposits are summed by true PDG, and an event is retained when one target PDG contributes at least 60% of the B-stack deposited energy. The target classes are proton (`2212`), deuteron (`1000010020`), alpha (`1000020040`), and carbon-12 (`1000060120`).",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        (
            f"Before truth modeling, the script rescanned HRD B-stack raw ROOT and reproduced the shared S00 selected-pulse count: "
            f"{raw_summary['selected_pulses']:,} selected pulses versus expected {raw_summary['expected_selected_pulses']:,} "
            f"(delta {raw_summary['delta']}). The selector is median baseline samples 0-3, physical B channels B2/B4/B6/B8 = 0/2/4/6, and `max(waveform-baseline) > 1000 ADC`."
        ),
        "",
        "## Methods",
        "",
        "For event \\(i\\), let \\(E_{ik}\\) be the GEANT4 B-stack energy deposit in scintillator layer \\(k\\in\\{0,\\dots,7\\}\\), \\(T_{ik}\\) its energy-weighted time, and \\(E_i=\\sum_k E_{ik}\\). The common sequence input is \\([\\log(1+E_{ik}), E_{ik}/E_i, T_{ik}/100]\\). Tabular features add \\(\\log(1+E_i)\\), first-layer charge, tail charge, tail/first ratio, layer centroid \\(\\mu_i=\\sum_k kE_{ik}/E_i\\), spread \\(\\sigma_i^2=\\sum_k (k-\\mu_i)^2E_{ik}/E_i\\), active-layer count, time moments, path-length sums, dE/dx proxy, and energy-weighted positions.",
        "",
        "The traditional method is a charge-comparison PSD / dE/dx band classifier: each species is represented by robust train-fold medians and IQR-derived diagonal scales in the handcrafted charge-shape variables, and the predicted species minimizes the robust squared band distance with train-fold class priors. Ridge is L2 multinomial logistic regression. Gradient-boosted trees use histogram gradient boosting with class-balanced sample weights. MLP is a scaled two-hidden-layer neural net. The 1D-CNN learns local layer-pattern filters over the sequence input. The new architecture, `hybrid_cnn_tabular`, concatenates the CNN embedding with standardized global tabular features before classification.",
        "",
        "Evaluation is leave-one-simulation-block-held-out. The GEANT4 file has no acquisition run field, so deterministic contiguous event-index blocks are used as run-like groups; all intervals are nonparametric bootstrap intervals over these held-out groups.",
        "",
        "## Class balance",
        "",
        md_table(class_counts, ["truth_class", "truth_pdg", "available_events", "used_events"], ".0f"),
        "",
        "## Method scoreboard",
        "",
        md_table(metrics, ["method", "balanced_accuracy", "balanced_accuracy_ci_low", "balanced_accuracy_ci_high", "macro_f1", "macro_f1_ci_low", "macro_f1_ci_high"]),
        "",
        "## Purity and efficiency",
        "",
        md_table(species[species["method"] == winner], ["species", "truth_n", "pred_n", "purity", "purity_ci_low", "purity_ci_high", "efficiency", "efficiency_ci_low", "efficiency_ci_high"]),
        "",
        "## Fold stability",
        "",
        md_table(fold[fold["method"] == winner], ["sim_run", "n", "balanced_accuracy"]),
        "",
        "## Leakage controls",
        "",
        md_table(leakage, ["check", "value", "threshold", "pass"]),
        "",
        "Identifier-only and shuffled-label controls are intentionally weak baselines. They do not prove absence of every simulation artifact, but they check that the reported accuracy is not a trivial event-index or block-label leak and that the pipeline is not scoring against a misaligned label vector.",
        "",
        "## Systematics and caveats",
        "",
        "- The study is a GEANT4 truth benchmark, not a claim that real test-beam events can be labeled without external truth.",
        "- `LayerID1 == 2` is used as the simulated B-stack index. A geometry-label mismatch would alter absolute performance; the raw HRD reproduction gate checks only detector-data parsing, not simulation geometry naming.",
        "- The event label is dominant deposited energy in the B-stack, so mixed showers and secondaries below the 60% dominance threshold are excluded rather than forced into a species.",
        "- GEANT4 deposits are amplitude proxies, not digitized waveforms. The sequence input captures longitudinal charge/time shape but not electronics response, thresholding, saturation, or noise in the real HRD waveforms.",
        "- Bootstrap intervals resample the deterministic simulation blocks. They measure block-to-block stability, not full uncertainty from beamline modeling, material budget, or physics-list variations.",
        "- Traditional dE/dx bands remain interpretable and competitive, but the winner should be re-tested after a digitization layer or external calibration labels are available.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_by_run.csv`, `class_counts.csv`, `method_metrics.csv`, `per_species_metrics.csv`, `fold_metrics.csv`, `confusion_matrix_winner.csv`, `leakage_checks.csv`, and this `REPORT.md` are in the report directory.",
    ]
    out.joinpath("REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/0000000009_1_pidfull.json")
    args = parser.parse_args()
    start = time.time()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    raw_by_run, raw_summary, raw_inputs = reproduce_raw_counts(config)
    print(f"raw reproduction passed: {raw_summary['selected_pulses']} selected pulses", flush=True)
    geant4_path = choose_geant4_path(config)
    meta_all, seq_all, tab_all, classes = extract_geant4_features(config, geant4_path)
    print(f"geant4 extraction complete: {len(meta_all)} available labeled events", flush=True)
    available = meta_all.groupby(["truth_class", "truth_pdg"]).size().reset_index(name="available_events")
    meta, seq, tab = balanced_subsample(meta_all, seq_all, tab_all, classes, config)
    print(f"balanced benchmark sample: {len(meta)} events", flush=True)
    used = meta.groupby(["truth_class", "truth_pdg"]).size().reset_index(name="used_events")
    class_counts = available.merge(used, on=["truth_class", "truth_pdg"], how="left").fillna(0)
    preds, fold, y = run_benchmarks(meta, seq, tab, classes, config)
    metrics, species = summarize_metrics(y, meta["sim_run"].to_numpy(dtype=int), preds, classes, config)
    leakage = leakage_checks(meta, tab, y, config)
    winner = str(metrics.iloc[0]["method"])
    cm = pd.DataFrame(confusion_matrix(y, preds[winner], labels=np.arange(len(classes))), index=[f"true_{c}" for c in classes], columns=[f"pred_{c}" for c in classes])

    raw_by_run.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    class_counts.to_csv(out / "class_counts.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    species.to_csv(out / "per_species_metrics.csv", index=False)
    fold.to_csv(out / "fold_metrics.csv", index=False)
    cm.to_csv(out / "confusion_matrix_winner.csv")
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    inputs = pd.concat(
        [
            raw_inputs,
            pd.DataFrame([{"file": str(geant4_path), "sha256": sha256_file(geant4_path), "bytes": geant4_path.stat().st_size}]),
            pd.DataFrame([{"file": str(config_path.relative_to(ROOT)), "sha256": sha256_file(config_path), "bytes": config_path.stat().st_size}]),
            pd.DataFrame([{"file": str(Path(__file__).resolve().relative_to(ROOT)), "sha256": sha256_file(Path(__file__).resolve()), "bytes": Path(__file__).resolve().stat().st_size}]),
        ],
        ignore_index=True,
    )
    inputs.to_csv(out / "input_sha256.csv", index=False)
    write_report(out, config, raw_summary, class_counts, metrics, species, fold, leakage, winner, geant4_path)

    result = {
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "winner": winner,
        "winner_metric": "run_block_heldout_balanced_accuracy",
        "winner_balanced_accuracy": float(metrics.iloc[0]["balanced_accuracy"]),
        "winner_balanced_accuracy_ci95": [float(metrics.iloc[0]["balanced_accuracy_ci_low"]), float(metrics.iloc[0]["balanced_accuracy_ci_high"])],
        "winner_macro_f1": float(metrics.iloc[0]["macro_f1"]),
        "raw_reproduction": raw_summary,
        "geant4_input": str(geant4_path),
        "truth_definition": "dominant Sci_bar LayerID1==2 deposited energy by target PDG, dominance >= 0.6",
        "classes": config["classes"],
        "n_available_labeled_events": int(len(meta_all)),
        "n_used_events": int(len(meta)),
        "methods": metrics.to_dict(orient="records"),
        "leakage_checks_passed": bool(leakage["pass"].all()),
        "next_tickets": [],
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "input_sha256.csv",
            "raw_reproduction_by_run.csv",
            "class_counts.csv",
            "method_metrics.csv",
            "per_species_metrics.csv",
            "fold_metrics.csv",
            "confusion_matrix_winner.csv",
            "leakage_checks.csv",
        ],
        "runtime_sec": float(time.time() - start),
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket": config["ticket"],
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "config": str(config_path.relative_to(ROOT)),
        "command": f"/home/billy/anaconda3/bin/python scripts/pidfull_0000000009_1.py --config {config_path.relative_to(ROOT)}",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "awkward": ak.__version__,
            "torch": getattr(torch, "__version__", None),
        },
        "runtime_sec": result["runtime_sec"],
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "winner": winner, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
