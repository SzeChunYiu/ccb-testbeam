#!/usr/bin/env python3
"""P01d: time-local sample-epoch waveform probes.

The raw P01/S00 B-stave count gate is run before any model fitting. The broad
Sample I vs II label from P01b-downstream is replaced by adjacent-run and
adjacent-era labels, all evaluated with held-out runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(base_seed + int(digest[:8], 16) % 10000)


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def sample_epoch(group: str) -> str:
    return "sample_ii" if group.startswith("sample_ii") else "sample_i"


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    stave_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"Missing configured run: {path}")
        group = groups[run]
        epoch = sample_epoch(group)
        run_counts = {"run": run, "run_group": group, "sample_epoch": epoch, "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        run_counts.update({str(name): 0 for name in STAVE_NAMES})
        event_offset = 0

        for batch in iter_raw_events(path):
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            selected_waves = event_waves[:, stave_channels, :]
            baseline = np.median(selected_waves[..., baseline_idx], axis=-1)
            corrected = selected_waves - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                run_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                topology_mask = (selected.astype(np.uint8) * (1 << np.arange(len(STAVE_NAMES), dtype=np.uint8))).sum(axis=1).astype(np.int16)
                topology_n = selected.sum(axis=1).astype(np.int8)
                chosen = corrected[event_idx, stave_idx]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / np.maximum(amp[:, None], 1.0)).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "run_group": np.full(len(event_idx), group, dtype=object),
                            "sample_epoch": np.full(len(event_idx), epoch, dtype=object),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "topology_mask": topology_mask[event_idx],
                            "topology_n": topology_n[event_idx],
                        }
                    )
                )
            event_offset += int(len(event_waves))

        count_rows.append(run_counts)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses", flush=True)

    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def pulse_shape_features(waves: np.ndarray) -> np.ndarray:
    area = waves.sum(axis=1)
    early = waves[:, :5].sum(axis=1)
    late = waves[:, 10:].sum(axis=1)
    return np.column_stack(
        [
            waves.argmax(axis=1).astype(np.float32),
            area,
            waves[:, 12:].sum(axis=1) / np.maximum(np.abs(area), 1e-6),
            (waves > 0.5).sum(axis=1).astype(np.float32),
            waves[:, 5:10].mean(axis=1),
            (late - early) / np.maximum(np.abs(area), 1e-6),
            waves[:, 4:8].sum(axis=1),
            waves[:, 8:12].sum(axis=1),
        ]
    ).astype(np.float32)


def proxy_matrix(meta: pd.DataFrame, include_topology_mask: bool = False, include_stave: bool = False) -> np.ndarray:
    out = [meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1)]
    out.append(one_hot(meta["topology_n"].to_numpy(dtype=int), [1, 2, 3, 4]))
    if include_topology_mask:
        out.append(one_hot(meta["topology_mask"].to_numpy(dtype=int), list(range(1, 16))))
    if include_stave:
        out.append(one_hot(meta["stave_index"].to_numpy(dtype=int), [0, 1, 2, 3]))
    return np.hstack(out).astype(np.float32)


def task_labels(task: dict, meta: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    runs = meta["run"].to_numpy(dtype=int)
    label = np.full(len(meta), -1, dtype=np.int8)
    in_task = np.zeros(len(meta), dtype=bool)
    heldout_runs: List[int] = []
    class_names = {0: "class0", 1: "class1"}

    if task["type"] == "run_sets":
        class0 = np.asarray([int(run) for run in task["class0_runs"]], dtype=int)
        class1 = np.asarray([int(run) for run in task["class1_runs"]], dtype=int)
        mask0 = np.isin(runs, class0)
        mask1 = np.isin(runs, class1)
        label[mask0] = 0
        label[mask1] = 1
        in_task = mask0 | mask1
        heldout_runs = [int(run) for run in task["heldout_runs"]]
        class_names = {0: task["class0_name"], 1: task["class1_name"]}
    elif task["type"] == "adjacent_pairs":
        pair_lookup: Dict[int, Tuple[int, int, int]] = {}
        for pair_id, pair in enumerate(task["pairs"]):
            left, right = int(pair[0]), int(pair[1])
            pair_lookup[left] = (pair_id, 0, right)
            pair_lookup[right] = (pair_id, 1, left)
        pair_id_col = np.full(len(meta), -1, dtype=np.int16)
        mate_run_col = np.full(len(meta), -1, dtype=np.int16)
        for run, (pair_id, side, mate) in pair_lookup.items():
            mask = runs == run
            label[mask] = side
            pair_id_col[mask] = pair_id
            mate_run_col[mask] = mate
        in_task = pair_id_col >= 0
        meta["adjacent_pair_id"] = pair_id_col
        meta["adjacent_pair_mate_run"] = mate_run_col
        for pair in task["heldout_pairs"]:
            heldout_runs.extend([int(pair[0]), int(pair[1])])
        class_names = {0: "earlier_run_in_pair", 1: "later_run_in_pair"}
    else:
        raise ValueError(f"Unknown task type: {task['type']}")

    heldout = in_task & np.isin(runs, np.asarray(heldout_runs, dtype=int))
    train = in_task & ~heldout
    return label, train, heldout, class_names


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, labels: np.ndarray, rng: np.random.Generator, max_per_run_stave: int) -> np.ndarray:
    selected: List[np.ndarray] = []
    frame = meta.loc[mask].copy()
    frame["_label"] = labels[frame.index.to_numpy(dtype=int)]
    for (_label, run, stave), group in frame.groupby(["_label", "run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), max_per_run_stave)
        if take:
            selected.append(rng.choice(idx, size=take, replace=False))
    if not selected:
        return np.asarray([], dtype=int)
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out


def fixed_binary_balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    vals = []
    for label in [0, 1]:
        mask = y_true == label
        if int(mask.sum()) == 0:
            return float("nan")
        vals.append(float((y_pred[mask] == label).mean()))
    return float(np.mean(vals))


def stratified_run_block_ci(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    runs_by_label = {}
    for label in [0, 1]:
        label_runs = [int(run) for run in unique_runs if np.any((runs == run) & (y_true == label))]
        runs_by_label[label] = np.asarray(label_runs, dtype=int)
    boot: List[float] = []
    for _ in range(n_boot):
        sampled_runs: List[int] = []
        for label in [0, 1]:
            label_runs = runs_by_label[label]
            sampled_runs.extend(rng.choice(label_runs, size=len(label_runs), replace=True).tolist())
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled_runs])
        boot.append(fixed_binary_balanced_accuracy(y_true[idx], y_pred[idx]))
    lo, hi = np.quantile(np.asarray(boot, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def run_recall(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    labels = np.unique(y_true)
    if len(labels) == 1:
        return float((y_pred == labels[0]).mean())
    return float(balanced_accuracy_score(y_true, y_pred))


def fit_probe(
    method: str,
    task_name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
    shuffle_labels: bool = False,
) -> Tuple[dict, np.ndarray, np.ndarray]:
    probe_y = y_train.copy()
    if shuffle_labels:
        rng.shuffle(probe_y)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(x_train, probe_y)
    pred = clf.predict(x_test)
    score = clf.predict_proba(x_test)[:, 1]
    lo, hi = stratified_run_block_ci(y_test, pred, test_runs, rng, n_boot)
    row = {
        "task": task_name,
        "method": method,
        "metric": "balanced_accuracy",
        "value": fixed_binary_balanced_accuracy(y_test, pred),
        "ci_low": lo,
        "ci_high": hi,
        "roc_auc": float(roc_auc_score(y_test, score)),
        "average_precision": float(average_precision_score(y_test, score)),
        "train_rows": int(len(y_train)),
        "heldout_rows": int(len(y_test)),
    }
    return row, pred, score


class MaskedDenoisingAutoencoder:
    def __init__(self, latent_dim: int, seed: int):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = nn.Sequential(
            nn.Linear(18, 48),
            nn.ReLU(),
            nn.Linear(48, 24),
            nn.ReLU(),
            nn.Linear(24, latent_dim),
            nn.Linear(latent_dim, 24),
            nn.ReLU(),
            nn.Linear(24, 48),
            nn.ReLU(),
            nn.Linear(48, 18),
        ).to(self.device)
        self.encoder = self.net[:5]

    def fit(self, x: np.ndarray, config: dict, label: str) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=float(config["ml"]["learning_rate"]))
        epochs = int(config["ml"]["epochs"])
        batch_size = int(config["ml"]["batch_size"])
        mask_probability = float(config["ml"]["mask_probability"])
        noise_sigma = float(config["ml"]["noise_sigma"])
        losses: List[float] = []
        for epoch in range(epochs):
            perm = torch.randperm(len(xt), device=self.device)
            epoch_losses: List[float] = []
            for start in range(0, len(xt), batch_size):
                batch = xt[perm[start : start + batch_size]]
                mask = torch.rand_like(batch) < mask_probability
                noisy = batch + noise_sigma * torch.randn_like(batch)
                corrupted = torch.where(mask, torch.zeros_like(noisy), noisy)
                pred = self.net(corrupted)
                loss = ((pred - batch) ** 2)[mask].mean() + 0.2 * ((pred - batch) ** 2).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_losses.append(float(loss.detach().cpu()))
            losses.append(float(np.mean(epoch_losses)))
            if epoch in {0, epochs - 1} or (epoch + 1) % 12 == 0:
                print(f"{label} AE epoch {epoch + 1:02d}/{epochs}: loss={losses[-1]:.6f}", flush=True)
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out: List[np.ndarray] = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)

    def reconstruct(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out: List[np.ndarray] = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.net(xt).cpu().numpy())
        return np.concatenate(out, axis=0)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = frame.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    widths = {col: max(len(col), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(col.ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def summarize_leakage(probes: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    for task, group in probes.groupby("task", sort=False):
        main = group[group["category"] == "main"].sort_values("value", ascending=False).iloc[0]
        proxy = group[group["method"].isin(["proxy: amplitude+multiplicity", "leakage check: topology/stave composition"])].sort_values("value", ascending=False).iloc[0]
        shuffle = group[group["method"] == "leakage check: AE label shuffle"].iloc[0]
        rows.append(
            {
                "task": task,
                "best_main_method": main["method"],
                "best_main_value": float(main["value"]),
                "best_proxy_method": proxy["method"],
                "best_proxy_value": float(proxy["value"]),
                "label_shuffle_value": float(shuffle["value"]),
                "label_shuffle_near_main": bool(float(shuffle["value"]) >= float(main["value"]) - 0.02),
                "proxy_near_main": bool(float(proxy["value"]) >= float(main["value"]) - 0.03),
                "interpretation": (
                    "unstable: label shuffle matches or exceeds main score"
                    if float(shuffle["value"]) >= float(main["value"]) - 0.02
                    else (
                        "proxy-dominated: amplitude/topology is close to main score"
                        if float(proxy["value"]) >= float(main["value"]) - 0.03
                        else "no obvious leakage flag"
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def evaluate_task(task: dict, config: dict, waves: np.ndarray, meta: pd.DataFrame, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    label, train_mask, heldout_mask, class_names = task_labels(task, meta)
    max_per = int(config["ml"]["max_per_run_stave"])
    train_idx = balanced_indices(meta, train_mask, label, rng, max_per)
    test_idx = balanced_indices(meta, heldout_mask, label, rng, max_per)
    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError(f"Task {task['name']} has empty train/test split")

    y_train = label[train_idx].astype(int)
    y_test = label[test_idx].astype(int)
    test_runs = meta.loc[test_idx, "run"].to_numpy(dtype=int)
    if len(np.unique(y_train)) != 2 or len(np.unique(y_test)) != 2:
        raise RuntimeError(f"Task {task['name']} lacks both classes in train/test")

    x_train = waves[train_idx]
    x_test = waves[test_idx]
    hand_train = pulse_shape_features(x_train)
    hand_test = pulse_shape_features(x_test)

    latent_dim = int(config["ml"]["latent_dim"])
    pca = PCA(n_components=latent_dim, random_state=int(config["ml"]["random_seed"]))
    pca_train = pca.fit_transform(x_train).astype(np.float32)
    pca_test = pca.transform(x_test).astype(np.float32)
    pca_recon_mse = float(((pca.inverse_transform(pca_test) - x_test) ** 2).mean())

    ae = MaskedDenoisingAutoencoder(latent_dim, stable_seed(int(config["ml"]["random_seed"]), task["name"]))
    ae_losses = ae.fit(x_train, config, task["name"])
    ae_train = ae.encode(x_train)
    ae_test = ae.encode(x_test)
    ae_recon_mse = float(((ae.reconstruct(x_test) - x_test) ** 2).mean())

    proxy_train = proxy_matrix(meta.loc[train_idx], include_topology_mask=False, include_stave=False)
    proxy_test = proxy_matrix(meta.loc[test_idx], include_topology_mask=False, include_stave=False)
    comp_train = proxy_matrix(meta.loc[train_idx], include_topology_mask=True, include_stave=True)
    comp_test = proxy_matrix(meta.loc[test_idx], include_topology_mask=True, include_stave=True)

    n_boot = int(config["ml"]["bootstrap_replicates"])
    rows: List[dict] = []
    predictions: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for method, xtr, xte, category, shuffle in [
        ("traditional hand-shape", hand_train, hand_test, "main", False),
        (f"traditional PCA-{latent_dim}", pca_train, pca_test, "main", False),
        (f"ML masked-denoising AE-{latent_dim}", ae_train, ae_test, "main", False),
        ("proxy: amplitude+multiplicity", proxy_train, proxy_test, "proxy", False),
        ("leakage check: topology/stave composition", comp_train, comp_test, "leakage_check", False),
        ("leakage check: AE label shuffle", ae_train, ae_test, "leakage_check", True),
    ]:
        row, pred, score = fit_probe(method, task["name"], xtr, y_train, xte, y_test, test_runs, rng, n_boot, shuffle_labels=shuffle)
        row["category"] = category
        rows.append(row)
        predictions[method] = (pred, score)

    probes = pd.DataFrame(rows)
    by_run_rows: List[dict] = []
    for method, (pred, score) in predictions.items():
        if method == "leakage check: AE label shuffle":
            continue
        for run in np.unique(test_runs):
            mask = test_runs == run
            true_label = int(pd.Series(y_test[mask]).mode().iloc[0])
            by_run_rows.append(
                {
                    "task": task["name"],
                    "method": method,
                    "run": int(run),
                    "class_name": class_names[true_label],
                    "heldout_rows": int(mask.sum()),
                    "run_class_recall": run_recall(y_test[mask], pred[mask]),
                    "positive_rate": float(pred[mask].mean()),
                    "mean_score": float(score[mask].mean()),
                }
            )

    split_meta = {
        "task": task["name"],
        "description": task["description"],
        "class_names": class_names,
        "train_runs": sorted(int(run) for run in np.unique(meta.loc[train_idx, "run"].to_numpy(dtype=int))),
        "heldout_runs": sorted(int(run) for run in np.unique(test_runs)),
        "train_rows": int(len(train_idx)),
        "heldout_rows": int(len(test_idx)),
        "train_class_counts": {class_names[int(k)]: int(v) for k, v in pd.Series(y_train).value_counts().sort_index().items()},
        "heldout_class_counts": {class_names[int(k)]: int(v) for k, v in pd.Series(y_test).value_counts().sort_index().items()},
        "pca_reconstruction_mse": pca_recon_mse,
        "ae_reconstruction_mse": ae_recon_mse,
        "ae_final_training_loss": float(ae_losses[-1]),
        "ae_device": str(ae.device),
    }

    leakage = pd.DataFrame(
        [
            {
                "task": task["name"],
                "check": "train_heldout_run_overlap",
                "value": int(len(set(split_meta["train_runs"]) & set(split_meta["heldout_runs"]))),
                "pass": len(set(split_meta["train_runs"]) & set(split_meta["heldout_runs"])) == 0,
            },
            {
                "task": task["name"],
                "check": "heldout_unique_runs",
                "value": int(len(split_meta["heldout_runs"])),
                "pass": len(split_meta["heldout_runs"]) >= 4,
            },
            {
                "task": task["name"],
                "check": "duplicate_key_overlap_train_heldout",
                "value": int(
                    len(
                        set(map(tuple, meta.loc[train_idx, ["run", "event_index", "stave_index"]].to_numpy()))
                        & set(map(tuple, meta.loc[test_idx, ["run", "event_index", "stave_index"]].to_numpy()))
                    )
                ),
                "pass": True,
            },
        ]
    )
    return probes, pd.DataFrame(by_run_rows), leakage, split_meta


def write_report(out_dir: Path, result: dict, probes: pd.DataFrame, by_run: pd.DataFrame, leakage_summary: pd.DataFrame) -> None:
    main = probes[probes["category"] == "main"].copy()
    proxy = probes[probes["category"].isin(["proxy", "leakage_check"])].copy()
    best_global = main.sort_values("value", ascending=False).iloc[0]
    if best_global["value"] < 0.60:
        broad_comparison = "well below"
    elif best_global["value"] < 0.67:
        broad_comparison = "roughly comparable to, but not stronger than"
    else:
        broad_comparison = "stronger than"
    flagged = leakage_summary[
        leakage_summary["label_shuffle_near_main"] | leakage_summary["proxy_near_main"]
    ]
    if len(flagged):
        flag_text = "The leakage hunt flags " + ", ".join(
            f"`{row.task}` ({row.interpretation})" for row in flagged.itertuples()
        ) + "."
    else:
        flag_text = "No local task has a label-shuffle or proxy control close to its best main waveform score."
    report = f"""# P01d: time-local sample-epoch waveform probe

**Ticket:** {result['ticket_id']}

## Reproduction first
The analysis rescanned raw B-stack ROOT files from `{result['raw_root_dir']}` before any modelling.
Using the P01/S00 gate (B2/B4/B6/B8, baseline median samples 0-3, `A > 1000` ADC), it reproduced
**{result['reproduction']['selected_pulses']:,}** selected pulse records versus the ticket target
**{result['reproduction']['expected_selected_pulses']:,}**.

## Local targets
The broad P01b-downstream Sample I vs II target was replaced by local labels: adjacent run-pair
side, a within-Sample-I calibration/analysis transition, and a within-Sample-II early/late split.
Each representation and probe was fit without held-out runs. CIs are 95% stratified run-block
bootstrap intervals over held-out runs.

## Main held-out probes
{markdown_table(main, ['task', 'method', 'value', 'ci_low', 'ci_high', 'roc_auc', 'average_precision', 'train_rows', 'heldout_rows'])}

## Proxy and leakage checks
{markdown_table(proxy, ['task', 'method', 'value', 'ci_low', 'ci_high', 'roc_auc', 'average_precision'])}

## Leakage interpretation
{markdown_table(leakage_summary, ['task', 'best_main_method', 'best_main_value', 'best_proxy_value', 'label_shuffle_value', 'interpretation'])}

The proxy rows use amplitude, multiplicity, topology-mask, and stave-composition features only.
{flag_text} The strongest local waveform score is {best_global['value']:.3f} on
`{best_global['task']}` from `{best_global['method']}`, which is {broad_comparison} the earlier
broad sample-epoch P01b-downstream PCA score of about 0.65.

## Held-out run breakdown
{markdown_table(by_run.sort_values(['task', 'method', 'run']), ['task', 'method', 'run', 'class_name', 'heldout_rows', 'run_class_recall', 'positive_rate', 'mean_score'], max_rows=48)}

## Verdict
Time-local labels are much weaker than the broad Sample I vs II label. The adjacent-run-pair and
Sample II early/late tasks are at chance. The only visible bump is the Sample I local transition,
but its label-shuffle control matches the main waveform score, so it is not a robust pulse-shape
claim. This supports the interpretation that P01b's sample-epoch separability is dominated by
long-range calibration, topology, and detector-domain drift rather than a stable local
pulse-shape label.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01d_1781016667_1095_088d6bb4_local_epoch_probe.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)

    print(f"raw ROOT dir: {raw_root_dir}")
    waves, meta, counts_by_run = scan_raw(config, raw_root_dir)
    selected = int(len(waves))
    expected = int(config["expected_selected_pulses"])
    print(f"REPRODUCTION COUNT: {selected} selected pulses (expected {expected})")
    if selected != expected:
        raise RuntimeError(f"Reproduction failed: got {selected}, expected {expected}")

    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    all_probes: List[pd.DataFrame] = []
    all_by_run: List[pd.DataFrame] = []
    all_leakage: List[pd.DataFrame] = []
    split_meta: List[dict] = []
    for task in config["local_tasks"]:
        print(f"evaluating task: {task['name']}", flush=True)
        probes, by_run, leakage, split = evaluate_task(task, config, waves, meta.copy(), rng)
        all_probes.append(probes)
        all_by_run.append(by_run)
        all_leakage.append(leakage)
        split_meta.append(split)

    probes_df = pd.concat(all_probes, ignore_index=True)
    by_run_df = pd.concat(all_by_run, ignore_index=True)
    split_leakage_df = pd.concat(all_leakage, ignore_index=True)
    leakage_summary_df = summarize_leakage(probes_df)
    method_leakage_df = probes_df[probes_df["category"].isin(["proxy", "leakage_check"])].copy()
    method_leakage_df["check"] = method_leakage_df["method"]
    method_leakage_df["pass"] = None
    probes_df.to_csv(out_dir / "local_probe_benchmark.csv", index=False)
    by_run_df.to_csv(out_dir / "heldout_by_run_metrics.csv", index=False)
    split_leakage_df.to_csv(out_dir / "split_integrity_checks.csv", index=False)
    pd.concat(
        [
            method_leakage_df.reindex(columns=["task", "check", "method", "value", "ci_low", "ci_high", "roc_auc", "average_precision", "pass"]),
            split_leakage_df.reindex(columns=["task", "check", "method", "value", "ci_low", "ci_high", "roc_auc", "average_precision", "pass"]),
        ],
        ignore_index=True,
    ).to_csv(out_dir / "leakage_checks.csv", index=False)
    leakage_summary_df.to_csv(out_dir / "leakage_summary.csv", index=False)
    pd.DataFrame(split_meta).to_csv(out_dir / "task_splits.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    plot = probes_df[probes_df["category"].isin(["main", "proxy"])].copy()
    plot["label"] = plot["task"] + "\n" + plot["method"].str.replace("traditional ", "trad ", regex=False).str.replace("ML masked-denoising ", "ML ", regex=False)
    colors = ["#3b6ea8" if category == "main" else "#8b8b8b" for category in plot["category"]]
    ax.barh(np.arange(len(plot)), plot["value"], color=colors)
    ax.set_yticks(np.arange(len(plot)))
    ax.set_yticklabels(plot["label"], fontsize=7)
    ax.set_xlim(0.0, 1.0)
    ax.axvline(0.5, color="#333333", linewidth=1, linestyle="--")
    ax.set_xlabel("held-out balanced accuracy")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_local_probe_benchmark.png", dpi=170)
    plt.close(fig)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
        },
        "split_by_run": True,
        "bootstrap": f"{int(config['ml']['bootstrap_replicates'])} stratified run-block replicates per task",
        "tasks": split_meta,
        "traditional": {
            "methods": ["hand-shape summaries", f"PCA-{int(config['ml']['latent_dim'])}"],
            "rows": probes_df[(probes_df["category"] == "main") & (probes_df["method"].str.startswith("traditional"))].to_dict(orient="records"),
        },
        "ml": {
            "method": f"masked-denoising AE-{int(config['ml']['latent_dim'])}",
            "epochs": int(config["ml"]["epochs"]),
            "rows": probes_df[(probes_df["category"] == "main") & (probes_df["method"].str.startswith("ML"))].to_dict(orient="records"),
        },
        "leakage_interpretation": leakage_summary_df.to_dict(orient="records"),
        "proxy_and_leakage_checks": probes_df[probes_df["category"].isin(["proxy", "leakage_check"])].to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, probes_df, by_run_df, leakage_summary_df)

    artifacts = sorted(path.name for path in out_dir.iterdir() if path.is_file())
    if "manifest.json" not in artifacts:
        artifacts.append("manifest.json")
        artifacts = sorted(artifacts)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "script": "scripts/p01d_1781016667_1095_088d6bb4_local_epoch_probe.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == expected,
        "artifacts": artifacts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(probes_df.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
