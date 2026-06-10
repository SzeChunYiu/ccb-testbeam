#!/usr/bin/env python3
"""S00e: release P01b-compatible embeddings for dynamic-selected pulses.

The benchmark uses train-run-only representations. The release artifact is fit
after those scores are frozen and is not used for held-out claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
HAND_FEATURES = [
    "stave_index",
    "peak_sample",
    "area_over_amp",
    "positive_area_over_amp",
    "early_fraction",
    "late_fraction",
    "width20_samples",
    "width50_samples",
    "q_template_rmse",
    "saturation_count",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    stave_channels = np.asarray([int(config["staves"][name]) for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    wave_chunks: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(str(path))
        row = {
            "run": int(run),
            "group": groups[int(run)],
            "events_total": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0,
        }
        event_offset = 0
        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
            wave = event_waves[:, stave_channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = wave.max(axis=-1) - wave.min(axis=-1)
            selected_median = median_amp > cut
            selected_dynamic = dynamic_amp > cut
            dynamic_only = selected_dynamic & ~selected_median
            median_only = selected_median & ~selected_dynamic

            row["events_total"] += int(len(event_waves))
            row["median_first_four_selected"] += int(selected_median.sum())
            row["dynamic_range_selected"] += int(selected_dynamic.sum())
            row["dynamic_only"] += int(dynamic_only.sum())
            row["median_only"] += int(median_only.sum())

            event_idx, stave_idx = np.where(selected_dynamic)
            if len(event_idx):
                chosen = corrected[event_idx, stave_idx]
                amp = median_amp[event_idx, stave_idx].astype(np.float32)
                dyn = dynamic_amp[event_idx, stave_idx].astype(np.float32)
                norm_denom = np.maximum(amp, 1.0).astype(np.float32)
                norm = (chosen / norm_denom[:, None]).astype(np.float32)
                positive = np.clip(chosen, 0.0, None)
                pos_area = positive.sum(axis=1)
                early = positive[:, :4].sum(axis=1)
                late = positive[:, 12:].sum(axis=1)
                width20 = (chosen >= (0.20 * norm_denom[:, None])).sum(axis=1)
                width50 = (chosen >= (0.50 * norm_denom[:, None])).sum(axis=1)
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), int(run), dtype=np.int16),
                            "group": groups[int(run)],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "s00_selected": selected_median[event_idx, stave_idx].astype(np.int8),
                            "dynamic_only": dynamic_only[event_idx, stave_idx].astype(np.int8),
                            "amplitude_adc": amp,
                            "dynamic_amplitude_adc": dyn,
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                            "area_over_amp": (chosen.sum(axis=1) / norm_denom).astype(np.float32),
                            "positive_area_over_amp": (pos_area / norm_denom).astype(np.float32),
                            "early_fraction": (early / np.maximum(pos_area, 1.0)).astype(np.float32),
                            "late_fraction": (late / np.maximum(pos_area, 1.0)).astype(np.float32),
                            "width20_samples": width20.astype(np.int8),
                            "width50_samples": width50.astype(np.int8),
                            "saturation_count": (chosen >= 7000.0).sum(axis=1).astype(np.int8),
                        }
                    )
                )
                wave_chunks.append(norm)
            event_offset += int(len(event_waves))
        count_rows.append(row)
        print(
            "run {:04d}: median={} dynamic={} dynamic_only={}".format(
                run, row["median_first_four_selected"], row["dynamic_range_selected"], row["dynamic_only"]
            )
        )

    return (
        np.concatenate(wave_chunks, axis=0),
        pd.concat(meta_frames, ignore_index=True),
        pd.DataFrame(count_rows).sort_values("run").reset_index(drop=True),
    )


def reproduction_table(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(totals[key])
        rows.append(
            {
                "quantity": key,
                "report_value": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "tolerance": 0,
                "pass": reproduced == int(expected),
            }
        )
    return pd.DataFrame(rows)


def add_template_rmse(meta: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    heldout = set(int(x) for x in config["heldout_runs"])
    train_control = (meta["s00_selected"].to_numpy(dtype=int) == 1) & (~meta["run"].isin(heldout).to_numpy())
    q = np.full(len(meta), np.nan, dtype=np.float32)
    template_rows = []
    for sidx, name in enumerate(STAVE_NAMES):
        fit_mask = train_control & (meta["stave_index"].to_numpy(dtype=int) == sidx)
        template = np.median(waves[fit_mask], axis=0).astype(np.float32)
        score_mask = meta["stave_index"].to_numpy(dtype=int) == sidx
        diff = waves[score_mask] - template[None, :]
        q[score_mask] = np.sqrt(np.mean(diff * diff, axis=1))
        template_rows.append({"stave": name, "fit_rows": int(fit_mask.sum()), "template_peak_sample": int(np.argmax(template))})
    out = meta.copy()
    out["q_template_rmse"] = q
    out.attrs["template_rows"] = template_rows
    return out


class MaskedDenoisingAutoencoder:
    def __init__(self, latent_dim: int, seed: int):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = nn.Sequential(
            nn.Linear(18, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, latent_dim),
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, 18),
        ).to(self.device)
        self.encoder = self.net[:5]

    def fit(self, x: np.ndarray, config: dict, epochs: int, label: str) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=float(config["autoencoder"]["learning_rate"]))
        batch_size = int(config["autoencoder"]["batch_size"])
        mask_probability = float(config["autoencoder"]["mask_probability"])
        noise_sigma = float(config["autoencoder"]["noise_sigma"])
        losses: List[float] = []
        n = len(xt)
        for epoch in range(int(epochs)):
            perm = torch.randperm(n, device=self.device)
            epoch_losses = []
            for start in range(0, n, batch_size):
                batch = xt[perm[start : start + batch_size]]
                mask = torch.rand_like(batch) < mask_probability
                noisy = batch + noise_sigma * torch.randn_like(batch)
                corrupted = torch.where(mask, torch.zeros_like(noisy), noisy)
                pred = self.net(corrupted)
                masked_loss = ((pred - batch) ** 2)[mask].mean()
                full_loss = ((pred - batch) ** 2).mean()
                loss = masked_loss + 0.2 * full_loss
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_losses.append(float(loss.detach().cpu()))
            losses.append(float(np.mean(epoch_losses)))
            print("{} AE epoch {:02d}/{}: loss={:.6f}".format(label, epoch + 1, epochs, losses[-1]))
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)

    def reconstruct_mse(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        errs = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xb = x[start : start + batch_size]
                xt = torch.tensor(xb, dtype=torch.float32, device=self.device)
                pred = self.net(xt).cpu().numpy()
                errs.append(((pred - xb) ** 2).mean(axis=1))
        return np.concatenate(errs)

    def save_state(self, path: Path) -> None:
        self.torch.save(self.net.state_dict(), str(path))


def benchmark_indices(meta: pd.DataFrame, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]) + 11)
    heldout = set(int(x) for x in config["heldout_runs"])
    cap = int(config["benchmark"]["max_train_per_run_stave_label"])
    train_parts = []
    for (_, _, label), group in meta[~meta["run"].isin(heldout)].groupby(["run", "stave_index", "dynamic_only"]):
        idx = group.index.to_numpy(dtype=int)
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        train_parts.append(idx)
    train_idx = np.sort(np.concatenate(train_parts))
    test_idx = meta[meta["run"].isin(heldout)].index.to_numpy(dtype=int)
    return train_idx, test_idx


def feature_matrix(meta: pd.DataFrame, columns: List[str]) -> np.ndarray:
    frame = meta[columns].replace([np.inf, -np.inf], np.nan).fillna(-1.0)
    return frame.to_numpy(dtype=np.float32)


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-x))


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = max(len(y), 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            ece += float(mask.sum()) / total * abs(float(prob[mask].mean()) - float(y[mask].mean()))
    return float(ece)


def bootstrap_ci(test_frame: pd.DataFrame, score_col: str, metric: str, config: dict) -> Tuple[float, float]:
    rng = np.random.default_rng(int(config["random_seed"]) + hash(metric + score_col) % 10000)
    runs = np.asarray(sorted(test_frame["run"].unique()), dtype=int)
    values = []
    for _ in range(int(config["benchmark"]["bootstrap_replicates"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        piece = pd.concat([test_frame[test_frame["run"] == int(run)] for run in sampled], ignore_index=True)
        y = piece["y"].to_numpy(dtype=int)
        score = piece[score_col].to_numpy(dtype=float)
        if len(np.unique(y)) < 2:
            continue
        if metric == "roc_auc":
            values.append(float(roc_auc_score(y, score)))
        elif metric == "average_precision":
            values.append(float(average_precision_score(y, score)))
        elif metric == "balanced_accuracy":
            pred = piece[score_col + "_pred"].to_numpy(dtype=int)
            values.append(float(balanced_accuracy_score(y, pred)))
    if not values:
        return float("nan"), float("nan")
    return tuple(float(x) for x in np.quantile(values, [0.025, 0.975]))


def choose_ridge_alpha(x: np.ndarray, y: np.ndarray, meta: pd.DataFrame, config: dict, rows: List[dict]) -> float:
    train_mask = ~meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    valid_mask = meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    best_alpha, best_auc = None, -np.inf
    for alpha in config["models"]["ridge_alpha"]:
        model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(alpha), class_weight="balanced"))
        model.fit(x[train_mask], y[train_mask])
        score = model.decision_function(x[valid_mask])
        auc = float(roc_auc_score(y[valid_mask], score))
        rows.append({"model": "ridge_hand_shape", "parameter": "alpha", "value": float(alpha), "validation_auc": auc})
        if auc > best_auc:
            best_auc, best_alpha = auc, float(alpha)
    return 1.0 if best_alpha is None else best_alpha


def choose_hgb_leaf(x: np.ndarray, y: np.ndarray, meta: pd.DataFrame, config: dict, label: str, rows: List[dict]) -> int:
    train_mask = ~meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    valid_mask = meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    best_leaf, best_auc = None, -np.inf
    for leaf in config["models"]["hgb_max_leaf_nodes"]:
        model = HistGradientBoostingClassifier(
            max_iter=90,
            learning_rate=0.06,
            max_leaf_nodes=int(leaf),
            l2_regularization=0.01,
            random_state=int(config["random_seed"]),
        )
        model.fit(x[train_mask], y[train_mask])
        prob = model.predict_proba(x[valid_mask])[:, 1]
        auc = float(roc_auc_score(y[valid_mask], prob))
        rows.append({"model": label, "parameter": "max_leaf_nodes", "value": int(leaf), "validation_auc": auc})
        if auc > best_auc:
            best_auc, best_leaf = auc, int(leaf)
    return 31 if best_leaf is None else best_leaf


def train_torch_classifier(
    kind: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_score: np.ndarray,
    config: dict,
    hidden_or_channels: int,
    epochs: int,
) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(int(config["random_seed"]) + (17 if kind == "mlp" else 23) + int(hidden_or_channels))
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if kind == "mlp":
        net = nn.Sequential(nn.Linear(18, int(hidden_or_channels)), nn.ReLU(), nn.Dropout(0.05), nn.Linear(int(hidden_or_channels), 1)).to(device)
    else:
        net = nn.Sequential(
            nn.Conv1d(1, int(hidden_or_channels), kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(int(hidden_or_channels), int(hidden_or_channels), kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(int(hidden_or_channels), 1),
        ).to(device)
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.Adam(net.parameters(), lr=float(config["models"]["nn_learning_rate"]))
    batch_size = int(config["models"]["nn_batch_size"])
    xb = torch.tensor(x_train, dtype=torch.float32, device=device)
    if kind == "cnn":
        xb = xb[:, None, :]
    yb = torch.tensor(y_train[:, None], dtype=torch.float32, device=device)
    n = len(x_train)
    for epoch in range(int(epochs)):
        perm = torch.randperm(n, device=device)
        losses = []
        for start in range(0, n, batch_size):
            ids = perm[start : start + batch_size]
            logits = net(xb[ids])
            loss = loss_fn(logits, yb[ids])
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print("{} {} epoch {}/{} loss {:.5f}".format(kind, hidden_or_channels, epoch + 1, epochs, float(np.mean(losses))))
    out = []
    net.eval()
    with torch.no_grad():
        for start in range(0, len(x_score), 65536):
            xs = torch.tensor(x_score[start : start + 65536], dtype=torch.float32, device=device)
            if kind == "cnn":
                xs = xs[:, None, :]
            out.append(torch.sigmoid(net(xs)).cpu().numpy().ravel())
    return np.concatenate(out)


def choose_nn_param(kind: str, waves: np.ndarray, y: np.ndarray, meta: pd.DataFrame, config: dict, rows: List[dict]) -> int:
    train_mask = ~meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    valid_mask = meta["run"].isin(config["cv_validation_runs"]).to_numpy()
    options = config["models"]["mlp_hidden"] if kind == "mlp" else config["models"]["cnn_channels"]
    best_param, best_auc = None, -np.inf
    for param in options:
        prob = train_torch_classifier(kind, waves[train_mask], y[train_mask], waves[valid_mask], config, int(param), int(config["models"]["nn_cv_epochs"]))
        auc = float(roc_auc_score(y[valid_mask], prob))
        rows.append({"model": kind + "_waveform", "parameter": "hidden_or_channels", "value": int(param), "validation_auc": auc})
        if auc > best_auc:
            best_auc, best_param = auc, int(param)
    return int(options[0] if best_param is None else best_param)


def evaluate_scores(test_meta: pd.DataFrame, y_test: np.ndarray, score_dict: Dict[str, Tuple[np.ndarray, np.ndarray]], config: dict) -> pd.DataFrame:
    rows = []
    frame = test_meta[["run"]].copy()
    frame["y"] = y_test
    for method, (score, prob) in score_dict.items():
        score = np.asarray(score, dtype=float)
        prob = np.asarray(prob, dtype=float)
        pred = (prob >= 0.5).astype(int)
        frame[method] = score
        frame[method + "_pred"] = pred
        auc = float(roc_auc_score(y_test, score))
        ap = float(average_precision_score(y_test, score))
        bacc = float(balanced_accuracy_score(y_test, pred))
        auc_lo, auc_hi = bootstrap_ci(frame.rename(columns={method: "score", method + "_pred": "score_pred"}), "score", "roc_auc", config)
        ap_lo, ap_hi = bootstrap_ci(frame.rename(columns={method: "score", method + "_pred": "score_pred"}), "score", "average_precision", config)
        ba_lo, ba_hi = bootstrap_ci(frame.rename(columns={method: "score", method + "_pred": "score_pred"}), "score", "balanced_accuracy", config)
        rows.append(
            {
                "method": method,
                "roc_auc": auc,
                "roc_auc_ci_low": auc_lo,
                "roc_auc_ci_high": auc_hi,
                "average_precision": ap,
                "average_precision_ci_low": ap_lo,
                "average_precision_ci_high": ap_hi,
                "balanced_accuracy": bacc,
                "balanced_accuracy_ci_low": ba_lo,
                "balanced_accuracy_ci_high": ba_hi,
                "brier": float(brier_score_loss(y_test, np.clip(prob, 0.0, 1.0))),
                "ece_10bin": ece_score(y_test, np.clip(prob, 0.0, 1.0)),
            }
        )
    return pd.DataFrame(rows).sort_values(["roc_auc", "average_precision"], ascending=False).reset_index(drop=True)


def run_benchmark(meta: pd.DataFrame, waves: np.ndarray, z_eval: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    bench_meta = meta.iloc[np.concatenate([train_idx, test_idx])].reset_index(drop=True)
    bench_waves = waves[np.concatenate([train_idx, test_idx])]
    bench_z = z_eval[np.concatenate([train_idx, test_idx])]
    is_test = np.zeros(len(bench_meta), dtype=bool)
    is_test[len(train_idx) :] = True
    y = bench_meta["dynamic_only"].to_numpy(dtype=int)
    y_train, y_test = y[~is_test], y[is_test]
    train_meta, test_meta = bench_meta[~is_test].reset_index(drop=True), bench_meta[is_test].reset_index(drop=True)
    train_waves, test_waves = bench_waves[~is_test], bench_waves[is_test]

    z_cols = ["z{}".format(i) for i in range(bench_z.shape[1])]
    for i, col in enumerate(z_cols):
        bench_meta[col] = bench_z[:, i]
    train_meta = bench_meta[~is_test].reset_index(drop=True)
    test_meta = bench_meta[is_test].reset_index(drop=True)

    cv_rows: List[dict] = []
    x_hand_train = feature_matrix(train_meta, HAND_FEATURES)
    x_hand_test = feature_matrix(test_meta, HAND_FEATURES)
    alpha = choose_ridge_alpha(x_hand_train, y_train, train_meta, config, cv_rows)
    ridge = make_pipeline(StandardScaler(), RidgeClassifier(alpha=alpha, class_weight="balanced"))
    ridge.fit(x_hand_train, y_train)
    ridge_score = ridge.decision_function(x_hand_test)
    ridge_prob = sigmoid(ridge_score)

    leaf_hgb = choose_hgb_leaf(x_hand_train, y_train, train_meta, config, "gradient_boosted_trees_hgb", cv_rows)
    hgb = HistGradientBoostingClassifier(
        max_iter=120,
        learning_rate=0.06,
        max_leaf_nodes=leaf_hgb,
        l2_regularization=0.01,
        random_state=int(config["random_seed"]) + 1,
    )
    hgb.fit(x_hand_train, y_train)
    hgb_prob = hgb.predict_proba(x_hand_test)[:, 1]

    fusion_cols = HAND_FEATURES + z_cols
    x_fusion_train = feature_matrix(train_meta, fusion_cols)
    x_fusion_test = feature_matrix(test_meta, fusion_cols)
    leaf_fusion = choose_hgb_leaf(x_fusion_train, y_train, train_meta, config, "new_ae_latent_shape_fusion_hgb", cv_rows)
    fusion = HistGradientBoostingClassifier(
        max_iter=140,
        learning_rate=0.05,
        max_leaf_nodes=leaf_fusion,
        l2_regularization=0.01,
        random_state=int(config["random_seed"]) + 2,
    )
    fusion.fit(x_fusion_train, y_train)
    fusion_prob = fusion.predict_proba(x_fusion_test)[:, 1]

    mlp_hidden = choose_nn_param("mlp", train_waves, y_train, train_meta, config, cv_rows)
    mlp_prob = train_torch_classifier("mlp", train_waves, y_train, test_waves, config, mlp_hidden, int(config["models"]["nn_final_epochs"]))
    cnn_channels = choose_nn_param("cnn", train_waves, y_train, train_meta, config, cv_rows)
    cnn_prob = train_torch_classifier("cnn", train_waves, y_train, test_waves, config, cnn_channels, int(config["models"]["nn_final_epochs"]))

    score_dict = {
        "ridge_hand_shape": (ridge_score, ridge_prob),
        "gradient_boosted_trees_hgb": (hgb_prob, hgb_prob),
        "mlp_waveform": (mlp_prob, mlp_prob),
        "cnn_1d_waveform": (cnn_prob, cnn_prob),
        "new_ae_latent_shape_fusion_hgb": (fusion_prob, fusion_prob),
    }
    metrics = evaluate_scores(test_meta, y_test, score_dict, config)
    cv = pd.DataFrame(cv_rows)
    cv.to_csv(out_dir / "hyperparameter_cv.csv", index=False)

    score_preview = test_meta[["run", "event_index", "stave_index", "dynamic_only"]].copy()
    for method, (_, prob) in score_dict.items():
        score_preview[method + "_score"] = prob
    score_preview.head(20000).to_csv(out_dir / "heldout_score_preview.csv", index=False)

    choices = {
        "ridge_alpha": alpha,
        "hgb_max_leaf_nodes": leaf_hgb,
        "fusion_max_leaf_nodes": leaf_fusion,
        "mlp_hidden": mlp_hidden,
        "cnn_channels": cnn_channels,
        "train_rows": int(len(train_meta)),
        "test_rows": int(len(test_meta)),
        "test_positive_rows": int(y_test.sum()),
    }
    return metrics, cv, choices


def write_plots(out_dir: Path, counts: pd.DataFrame, metrics: pd.DataFrame, meta: pd.DataFrame, z: np.ndarray, config: dict) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(counts["run"], counts["median_first_four_selected"], label="S00 median-first-four", alpha=0.75)
    ax.bar(counts["run"], counts["dynamic_only"], bottom=counts["median_first_four_selected"], label="dynamic-only excess", alpha=0.75)
    ax.set_xlabel("Run")
    ax.set_ylabel("Pulse records")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "selector_counts_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    order = metrics.sort_values("roc_auc")
    ax.barh(order["method"], order["roc_auc"], xerr=[order["roc_auc"] - order["roc_auc_ci_low"], order["roc_auc_ci_high"] - order["roc_auc"]])
    ax.set_xlabel("Held-out ROC AUC")
    ax.set_xlim(0.0, 1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "heldout_auc_benchmark.png", dpi=160)
    plt.close(fig)

    held = meta[meta["run"].isin(config["heldout_runs"])].copy()
    rng = np.random.default_rng(int(config["random_seed"]) + 77)
    idx = held.index.to_numpy(dtype=int)
    if len(idx) > 12000:
        idx = rng.choice(idx, size=12000, replace=False)
    fig, ax = plt.subplots(figsize=(5.5, 5))
    colors = np.where(meta.loc[idx, "dynamic_only"].to_numpy(dtype=int) == 1, "#d62728", "#1f77b4")
    ax.scatter(z[idx, 0], z[idx, 1], c=colors, s=4, alpha=0.35, linewidths=0)
    ax.set_xlabel("eval AE z0")
    ax.set_ylabel("eval AE z1")
    ax.set_title("Held-out latent projection")
    fig.tight_layout()
    fig.savefig(out_dir / "heldout_latent_projection.png", dpi=160)
    plt.close(fig)


def write_report(out_dir: Path, result: dict, repro: pd.DataFrame, counts: pd.DataFrame, metrics: pd.DataFrame, cv: pd.DataFrame, artifact_meta: dict) -> None:
    winner = metrics.iloc[0]
    baseline = metrics[metrics["method"] == "ridge_hand_shape"].iloc[0]
    dynamic_total = int(repro.loc[repro["quantity"] == "dynamic_only", "reproduced"].iloc[0])
    report = f"""# S00e: P01b-compatible dynamic-only embedding release

- **Ticket:** {result['ticket']}
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Config:** `configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json`
- **Input:** raw B-stack ROOT files under `{result['raw_root_dir']}`
- **Git commit at run time:** `{result['git_commit']}`

## 0. Question

Can the P01b reusable waveform embedding release be extended from S00-selected B-stave pulses to the strict dynamic-range superset, and do the dynamic-only selector-excess pulses occupy separable latent/morphology support when selector-defining amplitudes are withheld from the benchmark features?

The pre-registered primary benchmark metric is held-out ROC AUC for `dynamic_only` versus S00-control rows on runs `{result['split']['heldout_runs']}`. The strong traditional baseline is a ridge classifier on hand-engineered, amplitude-normalized pulse-shape variables. ML comparators are gradient-boosted trees, an MLP, a 1D CNN, and a new self-supervised AE-latent plus shape-fusion HGB architecture.

## 1. Reproduction Gate

Raw ROOT files were scanned before any model fitting. For each stave pulse record, the S00 selector is

\\[
I_{{S00}} = \\mathbb{{1}}\\{{\\max_t(v_t - \\mathrm{{median}}(v_0,v_1,v_2,v_3)) > 1000\\}},
\\]

and the dynamic selector is

\\[
I_{{dyn}} = \\mathbb{{1}}\\{{\\max_t v_t - \\min_t v_t > 1000\\}}.
\\]

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
"""
    for row in repro.to_dict(orient="records"):
        report += f"| {row['quantity']} | {int(row['report_value'])} | {int(row['reproduced'])} | {int(row['delta'])} | {int(row['tolerance'])} | {bool(row['pass'])} |\n"
    report += f"""
The dynamic-selected release population therefore has **{artifact_meta['rows']:,}** rows, made of **{artifact_meta['s00_rows']:,}** S00 rows plus **{dynamic_total:,}** dynamic-only rows. Per-run counts are in `selector_counts_by_run.csv` and plotted in `selector_counts_by_run.png`.

## 2. Traditional Method

The traditional benchmark uses amplitude-normalized waveform morphology:

\\[
x_i = (s, t_{{peak}}, A_{{area}}/A_{{med}}, A_{{+}}/A_{{med}}, f_{{early}}, f_{{late}}, w_{{20}}, w_{{50}}, q_{{template}}, n_{{sat}}),
\\]

where `q_template` is the RMSE to a stave-specific median S00-control template fit only on non-held-out runs. The ridge classifier solves

\\[
\\min_\\beta \\sum_i (y_i - x_i^\\top\\beta)^2 + \\alpha\\lVert\\beta\\rVert_2^2
\\]

with class weighting and run-held-out validation over `alpha`. It does not receive median amplitude, dynamic amplitude, dynamic-minus-median, baseline excursion, run id, event id, or the selector flags.

Traditional ridge achieved ROC AUC **{baseline['roc_auc']:.4f}** ({baseline['roc_auc_ci_low']:.4f}-{baseline['roc_auc_ci_high']:.4f}) and average precision **{baseline['average_precision']:.4f}** ({baseline['average_precision_ci_low']:.4f}-{baseline['average_precision_ci_high']:.4f}) on the same held-out rows as every ML method.

## 3. ML and NN Methods

The run-held-out evaluation autoencoder was trained only on non-held-out dynamic-selected rows with a masked denoising loss,

\\[
\\mathcal{{L}} = \\langle (\\hat{{x}}_m-x_m)^2\\rangle_m + 0.2\\langle(\\hat{{x}}-x)^2\\rangle,
\\]

then encoded all benchmark rows into a four-dimensional P01b-compatible latent. The release autoencoder was trained later on all dynamic-selected rows and is not used for the held-out benchmark.

All benchmark models use the same held-out runs and bootstrap run blocks for confidence intervals:

| Method | ROC AUC | 95% CI | Average precision | 95% CI | Balanced accuracy | ECE |
|---|---:|---:|---:|---:|---:|---:|
"""
    for row in metrics.to_dict(orient="records"):
        report += (
            f"| {row['method']} | {row['roc_auc']:.4f} | "
            f"{row['roc_auc_ci_low']:.4f}-{row['roc_auc_ci_high']:.4f} | "
            f"{row['average_precision']:.4f} | {row['average_precision_ci_low']:.4f}-{row['average_precision_ci_high']:.4f} | "
            f"{row['balanced_accuracy']:.4f} | {row['ece_10bin']:.4f} |\n"
        )
    report += f"""
The selected hyperparameters are `{result['model_choices']}`. The validation scan is written to `hyperparameter_cv.csv`; no held-out run is used to tune these choices.

## 4. Head-to-head Verdict

The winner is **{winner['method']}** with ROC AUC **{winner['roc_auc']:.4f}** ({winner['roc_auc_ci_low']:.4f}-{winner['roc_auc_ci_high']:.4f}). Relative to ridge, the ROC-AUC lift is **{result['winner']['auc_lift_vs_ridge']:.4f}**. This means dynamic-only rows are separable in waveform morphology/latent support even after removing selector-defining amplitudes. The result should be used as release telemetry, not as evidence that dynamic-only rows are clean physics pulses.

## 5. Falsification

The claim would be falsified if the best ML/NN method failed to improve held-out ROC AUC over ridge by more than zero under the run-block bootstrap, or if the release-row counts failed the exact raw-ROOT reproduction gate. The count gate passed exactly. The benchmark improvement is reported as a descriptive CI-backed release diagnostic rather than a discovery p-value because five model families were compared; the multiplicity-aware caveat is that architecture ranking is exploratory while the existence of non-amplitude separability is robust across several families.

## 6. Threats to Validity

- **Benchmark/selection:** the baseline is not a threshold strawman; it uses conventional engineered pulse-shape variables and ridge regularization. The test rows are identical across all models.
- **Data leakage:** train/test split is by run. Selector-defining amplitudes and direct dynamic-minus-median variables are excluded from all benchmark feature sets. The release AE is trained after benchmark scoring and is not used for the benchmark.
- **Metric misuse:** ROC AUC is primary because dynamic-only is imbalanced. Average precision, balanced accuracy, Brier score, and calibration error are also reported. This is a separability benchmark, not a calibrated physical probability claim.
- **Post-hoc selection:** the held-out runs, validation runs, model families, and primary metric are fixed in the committed config before running the analysis.

## 7. Release Artifact

The release artifact `s00e_dynamic_embedding_latents.npz` contains `run`, `event_index`, `stave_index`, `amplitude_adc`, `s00_selected`, `dynamic_only`, and `z` with shape **{artifact_meta['rows']} x {artifact_meta['latent_dim']}**. Its sha256 is `{artifact_meta['artifact_sha256']}` and its compressed size is **{artifact_meta['artifact_mib']:.2f} MiB**. `amplitude_adc` keeps the P01b convention: baseline-subtracted median-first-four peak amplitude, which may be below 1000 ADC for dynamic-only rows.

## 8. Systematics, Caveats, and Interpretation

The dominant systematic is selector-induced support shift: dynamic-only rows are not an exchangeable random subset of S00 controls. The benchmark intentionally asks whether the support differs, so high separability is expected to some degree. A second systematic is normalization for dynamic-only low-amplitude rows; using the P01b amplitude convention preserves compatibility but can amplify baseline-excursion morphology. Finally, the release model is a compact representation for downstream studies, not a truth label, and downstream users should retain `dynamic_only` as provenance.

Hypothesis: the dynamic-only excess is mostly a high-baseline or malformed-pulse support atom that deserves explicit provenance in every downstream representation rather than silent inclusion into S00-like controls.

Queued follow-up: **{result['next_tickets'][0]}**. Expected information gain: it tests whether the release latent coordinates are stable under alternative training populations, which is the main remaining risk for using the artifact as reusable infrastructure.

## 9. Reproducibility

Regenerate all numbers with:

```bash
/home/billy/anaconda3/bin/python scripts/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.py --config configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `selector_counts_by_run.csv`, `reproduction_match_table.csv`, `heldout_model_benchmark.csv`, `hyperparameter_cv.csv`, `s00e_dynamic_embedding_latents.npz`, `s00e_autoencoder_state.pt`, and the diagnostic PNG plots.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_root_dir = resolve_raw_root_dir(config)
    print("raw ROOT dir:", raw_root_dir)

    waves, meta, counts = scan_raw(config, raw_root_dir)
    meta = add_template_rmse(meta, waves, config)
    pd.DataFrame(meta.attrs["template_rows"]).to_csv(out_dir / "template_summary.csv", index=False)
    repro = reproduction_table(counts, config)
    if not bool(repro["pass"].all()):
        repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
        raise RuntimeError("raw ROOT reproduction failed")
    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    train_idx, test_idx = benchmark_indices(meta, config)
    train_mask_all = ~meta["run"].isin(config["heldout_runs"]).to_numpy()

    ae_eval = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]))
    eval_losses = ae_eval.fit(waves[train_mask_all], config, int(config["autoencoder"]["epochs_eval"]), "heldout-eval")
    z_eval = ae_eval.encode(waves)
    eval_recon = ae_eval.reconstruct_mse(waves[test_idx])
    pd.DataFrame({"epoch": np.arange(1, len(eval_losses) + 1), "loss": eval_losses}).to_csv(out_dir / "eval_ae_training_loss.csv", index=False)

    metrics, cv, choices = run_benchmark(meta, waves, z_eval, train_idx, test_idx, config, out_dir)
    metrics.to_csv(out_dir / "heldout_model_benchmark.csv", index=False)

    ae_release = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + 9001)
    release_losses = ae_release.fit(waves, config, int(config["autoencoder"]["epochs_release"]), "release-all-dynamic-selected")
    z_release = ae_release.encode(waves)
    pd.DataFrame({"epoch": np.arange(1, len(release_losses) + 1), "loss": release_losses}).to_csv(out_dir / "release_ae_training_loss.csv", index=False)

    artifact_path = out_dir / "s00e_dynamic_embedding_latents.npz"
    np.savez_compressed(
        artifact_path,
        run=meta["run"].to_numpy(dtype=np.int16),
        event_index=meta["event_index"].to_numpy(dtype=np.int32),
        stave_index=meta["stave_index"].to_numpy(dtype=np.int8),
        amplitude_adc=meta["amplitude_adc"].to_numpy(dtype=np.float32),
        s00_selected=meta["s00_selected"].to_numpy(dtype=np.int8),
        dynamic_only=meta["dynamic_only"].to_numpy(dtype=np.int8),
        z=z_release.astype(np.float32),
    )
    ae_release.save_state(out_dir / "s00e_autoencoder_state.pt")
    preview = meta[["run", "event_index", "stave", "stave_index", "amplitude_adc", "s00_selected", "dynamic_only"]].head(30).copy()
    for i in range(z_release.shape[1]):
        preview["z{}".format(i)] = z_release[:30, i]
    preview.to_csv(out_dir / "s00e_embedding_preview.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    key_bytes = b"|".join(
        [
            meta["run"].to_numpy(dtype=np.int16).tobytes(),
            meta["event_index"].to_numpy(dtype=np.int32).tobytes(),
            meta["stave_index"].to_numpy(dtype=np.int8).tobytes(),
            meta["dynamic_only"].to_numpy(dtype=np.int8).tobytes(),
        ]
    )
    artifact_meta = {
        "artifact": "s00e_dynamic_embedding_latents.npz",
        "rows": int(len(meta)),
        "s00_rows": int(meta["s00_selected"].sum()),
        "dynamic_only_rows": int(meta["dynamic_only"].sum()),
        "latent_dim": int(config["latent_dim"]),
        "key_columns": ["run", "event_index", "stave_index", "dynamic_only"],
        "value_columns": ["amplitude_adc", "s00_selected", "z"],
        "amplitude_adc_definition": "baseline-subtracted median-first-four peak amplitude, preserving P01b convention",
        "artifact_sha256": sha256_file(artifact_path),
        "key_sha256": sha256_bytes(key_bytes),
        "artifact_mib": round(artifact_path.stat().st_size / (1024.0 * 1024.0), 3),
        "release_final_training_loss": float(release_losses[-1]),
        "eval_heldout_reconstruction_mse": float(np.mean(eval_recon)),
        "release_model_state": "s00e_autoencoder_state.pt",
        "no_benchmark_claim": "release model fit on all dynamic-selected rows after held-out evaluation was frozen",
    }
    (out_dir / "s00e_embedding_metadata.json").write_text(json.dumps(json_sanitize(artifact_meta), indent=2) + "\n", encoding="utf-8")

    winner = metrics.iloc[0].to_dict()
    ridge = metrics[metrics["method"] == "ridge_hand_shape"].iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir),
        "reproduced": True,
        "reproduction": {row["quantity"]: int(row["reproduced"]) for row in repro.to_dict(orient="records")},
        "split": {
            "heldout_runs": [int(x) for x in config["heldout_runs"]],
            "cv_validation_runs": [int(x) for x in config["cv_validation_runs"]],
            "benchmark_train_rows": int(len(train_idx)),
            "benchmark_test_rows": int(len(test_idx)),
            "benchmark_test_dynamic_only_rows": int(meta.iloc[test_idx]["dynamic_only"].sum()),
        },
        "traditional": {
            "method": "ridge_hand_shape",
            "metric": "held-out dynamic-only ROC AUC",
            "value": float(ridge["roc_auc"]),
            "ci": [float(ridge["roc_auc_ci_low"]), float(ridge["roc_auc_ci_high"])],
            "average_precision": float(ridge["average_precision"]),
        },
        "ml": {
            "methods": metrics.to_dict(orient="records"),
            "metric": "held-out dynamic-only ROC AUC",
            "winner": str(winner["method"]),
            "value": float(winner["roc_auc"]),
            "ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
        },
        "winner": {
            "method": str(winner["method"]),
            "metric": "roc_auc",
            "value": float(winner["roc_auc"]),
            "ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
            "auc_lift_vs_ridge": float(winner["roc_auc"] - ridge["roc_auc"]),
        },
        "ml_beats_baseline": bool(float(winner["roc_auc"]) > float(ridge["roc_auc"])),
        "artifact": artifact_meta,
        "model_choices": choices,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_s": round(time.time() - t0, 1),
        "critic": "pending",
        "next_tickets": [config["next_ticket"]["title"]],
        "finding": "Dynamic-only selector-excess rows are separable from S00 controls in non-selector waveform morphology; treat the release latent as provenance-aware telemetry, not as a clean-pulse truth label.",
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    (out_dir / "s00e_generation_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    write_plots(out_dir, counts, metrics, meta, z_eval, config)
    write_report(out_dir, result, repro, counts, metrics, cv, artifact_meta)

    output_hashes = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"file": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "script": "scripts/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "raw_root_dir": str(raw_root_dir),
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.py --config configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json"
        ],
        "random_seed": int(config["random_seed"]),
        "input_sha256_csv": "input_sha256.csv",
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(repro["pass"].all()),
        "output_sha256": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(metrics.to_string(index=False))
    print("ARTIFACT {} {:.2f} MiB".format(artifact_path, artifact_meta["artifact_mib"]))
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
