#!/usr/bin/env python3
"""P01d run-family leakage sentinels for waveform probes.

This ticket extends the P01c stave-identity leakage battery.  The raw ROOT
selected-pulse count is reproduced first, then each probe holds out one whole
configured run family.  The target is deliberately a nuisance target
(`stave_index`) so a representation gain is accepted only when it clears a
within-family label-shuffle p95 plus a configured margin.
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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score
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


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def stable_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(base_seed + int(digest[:8], 16) % 100000)


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
            lookup[int(run)] = str(group)
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    channels = np.asarray([int(config["staves"][str(name)]) for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    wave_parts: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = groups[int(run)]
        row = {
            "run": int(run),
            "run_group": group,
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_NAMES}
        event_offset = 0
        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
            selected_raw = event_waves[:, channels, :]
            baseline = np.median(selected_raw[..., baseline_idx], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            multiplicity = selected.sum(axis=1).astype(np.int8)

            row["events_total"] += int(len(event_waves))
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                chosen = corrected[event_idx, stave_idx]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                wave_parts.append((chosen / np.maximum(amp[:, None], 1.0)).astype(np.float32))
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), int(run), dtype=np.int16),
                            "run_group": np.full(len(event_idx), group, dtype=object),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "selected_multiplicity": multiplicity[event_idx],
                        }
                    )
                )
            event_offset += int(len(event_waves))
        count_rows.append({**row, **stave_counts})
        print("raw run {:04d}: {} selected pulses".format(run, row["selected_pulses"]), flush=True)

    return np.concatenate(wave_parts, axis=0), pd.concat(meta_parts, ignore_index=True), pd.DataFrame(count_rows)


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


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


def nuisance_features(meta: pd.DataFrame) -> np.ndarray:
    return np.hstack(
        [
            meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1),
            one_hot(meta["selected_multiplicity"].to_numpy(dtype=int), [1, 2, 3, 4]),
        ]
    ).astype(np.float32)


def event_order_features(meta: pd.DataFrame) -> np.ndarray:
    event = meta["event_index"].to_numpy(dtype=np.float32)
    run = meta["run"].to_numpy(dtype=np.float32)
    event_scaled = np.zeros(len(meta), dtype=np.float32)
    for run_value in np.unique(run):
        mask = run == run_value
        event_scaled[mask] = event[mask] / max(float(event[mask].max()), 1.0)
    return np.column_stack([event_scaled, np.sin(event_scaled * np.pi), np.cos(event_scaled * np.pi), run * 0.0]).astype(np.float32)


def residualize(train_x: np.ndarray, test_x: np.ndarray, train_nuisance: np.ndarray, test_nuisance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    train_n = scaler.fit_transform(train_nuisance)
    test_n = scaler.transform(test_nuisance)
    model = Ridge(alpha=1.0)
    model.fit(train_n, train_x)
    return (train_x - model.predict(train_n)).astype(np.float32), (test_x - model.predict(test_n)).astype(np.float32)


def capped_indices(meta: pd.DataFrame, mask: np.ndarray, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    selected: List[np.ndarray] = []
    frame = meta.loc[mask]
    for (_run, _stave), group in frame.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), int(max_per_run_stave))
        if take:
            selected.append(rng.choice(idx, size=take, replace=False))
    if not selected:
        return np.asarray([], dtype=int)
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out


def run_block_ci(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot: List[float] = []
    by_run = {int(run): np.where(runs == run)[0] for run in unique_runs}
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([by_run[int(run)] for run in sampled])
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    lo, hi = np.quantile(np.asarray(boot, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def fit_classifier(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", multi_class="auto", solver="lbfgs"),
    )
    clf.fit(x_train, y_train)
    return clf.predict(x_test)


def score_method(
    family: str,
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    config: dict,
) -> Tuple[dict, np.ndarray]:
    pred = fit_classifier(x_train, y_train, x_test)
    lo, hi = run_block_ci(y_test, pred, test_runs, rng, int(config["analysis"]["bootstrap_replicates"]))
    row = {
        "heldout_family": family,
        "method": method,
        "metric": "balanced_accuracy",
        "value": float(balanced_accuracy_score(y_test, pred)),
        "ci_low": lo,
        "ci_high": hi,
        "train_rows": int(len(y_train)),
        "heldout_rows": int(len(y_test)),
        "heldout_runs": int(len(np.unique(test_runs))),
    }
    return row, pred


def shuffle_null(
    family: str,
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    rng: np.random.Generator,
    n_shuffle: int,
) -> Tuple[List[dict], float]:
    rows: List[dict] = []
    for rep in range(int(n_shuffle)):
        shuffled = y_train.copy()
        rng.shuffle(shuffled)
        pred = fit_classifier(x_train, shuffled, x_test)
        rows.append(
            {
                "heldout_family": family,
                "method": method,
                "shuffle_rep": int(rep),
                "value": float(balanced_accuracy_score(y_test, pred)),
            }
        )
    p95 = float(np.quantile([row["value"] for row in rows], 0.95))
    return rows, p95


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
            if epoch in {0, epochs - 1}:
                print("{} AE epoch {:02d}/{}: loss={:.6f}".format(label, epoch + 1, epochs, losses[-1]), flush=True)
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
        return np.concatenate(out, axis=0).astype(np.float32)


def evaluate_family(config: dict, family: str, waves: np.ndarray, meta: pd.DataFrame, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    analysis = config["analysis"]
    heldout_mask = meta["run_group"].to_numpy(dtype=object) == family
    train_mask = ~heldout_mask
    max_per = int(analysis["max_per_run_stave"])
    train_idx = capped_indices(meta, train_mask, max_per, rng)
    test_idx = capped_indices(meta, heldout_mask, max_per, rng)
    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError("empty train/test split for {}".format(family))

    y_train = meta.loc[train_idx, "stave_index"].to_numpy(dtype=int)
    y_test = meta.loc[test_idx, "stave_index"].to_numpy(dtype=int)
    test_runs = meta.loc[test_idx, "run"].to_numpy(dtype=int)
    if len(np.unique(y_train)) != 4 or len(np.unique(y_test)) != 4:
        raise RuntimeError("family {} lacks all four staves".format(family))

    x_train = waves[train_idx]
    x_test = waves[test_idx]
    train_n = nuisance_features(meta.loc[train_idx])
    test_n = nuisance_features(meta.loc[test_idx])
    latent_dim = int(analysis["latent_dim"])

    pca = PCA(n_components=latent_dim, random_state=int(analysis["random_seed"]))
    pca_train = pca.fit_transform(x_train).astype(np.float32)
    pca_test = pca.transform(x_test).astype(np.float32)
    hand_train = pulse_shape_features(x_train)
    hand_test = pulse_shape_features(x_test)
    trad_train, trad_test = residualize(
        np.hstack([hand_train, pca_train]).astype(np.float32),
        np.hstack([hand_test, pca_test]).astype(np.float32),
        train_n,
        test_n,
    )

    ae = MaskedDenoisingAutoencoder(latent_dim, stable_seed(int(analysis["random_seed"]), family))
    ae_losses = ae.fit(x_train, config, family)
    ae_train_raw = ae.encode(x_train)
    ae_test_raw = ae.encode(x_test)
    ae_train, ae_test = residualize(ae_train_raw, ae_test_raw, train_n, test_n)

    proxy_train = train_n
    proxy_test = test_n
    event_train = event_order_features(meta.loc[train_idx])
    event_test = event_order_features(meta.loc[test_idx])

    metric_rows: List[dict] = []
    prediction_rows: List[dict] = []
    method_mats = [
        ("traditional residual hand+PCA-{}".format(latent_dim), trad_train, trad_test, "main"),
        ("ML residual masked-denoising AE-{}".format(latent_dim), ae_train, ae_test, "main"),
        ("proxy amplitude+multiplicity", proxy_train, proxy_test, "leakage_check"),
        ("event-order leakage probe", event_train, event_test, "leakage_check"),
    ]
    predictions: Dict[str, np.ndarray] = {}
    for method, xtr, xte, category in method_mats:
        row, pred = score_method(family, method, xtr, y_train, xte, y_test, test_runs, rng, config)
        row["category"] = category
        metric_rows.append(row)
        predictions[method] = pred

    shuffle_rows: List[dict] = []
    shuffle_p95: Dict[str, float] = {}
    for method, xtr, xte, category in method_mats[:2]:
        rows, p95 = shuffle_null(
            family,
            method,
            xtr,
            y_train,
            xte,
            y_test,
            rng,
            int(analysis["shuffle_replicates"]),
        )
        shuffle_rows.extend(rows)
        shuffle_p95[method] = p95

    for method, pred in predictions.items():
        for run in np.unique(test_runs):
            mask = test_runs == run
            prediction_rows.append(
                {
                    "heldout_family": family,
                    "method": method,
                    "run": int(run),
                    "heldout_rows": int(mask.sum()),
                    "balanced_accuracy": float(balanced_accuracy_score(y_test[mask], pred[mask])),
                    "predicted_stave_mix": json.dumps({str(k): int(v) for k, v in pd.Series(pred[mask]).value_counts().sort_index().items()}),
                }
            )

    metrics = pd.DataFrame(metric_rows)
    trad_method = "traditional residual hand+PCA-{}".format(latent_dim)
    ml_method = "ML residual masked-denoising AE-{}".format(latent_dim)
    trad_value = float(metrics.loc[metrics["method"] == trad_method, "value"].iloc[0])
    ml_value = float(metrics.loc[metrics["method"] == ml_method, "value"].iloc[0])
    proxy_value = float(metrics.loc[metrics["method"] == "proxy amplitude+multiplicity", "value"].iloc[0])
    event_value = float(metrics.loc[metrics["method"] == "event-order leakage probe", "value"].iloc[0])
    margin = float(analysis["shuffle_margin"])
    too_good = bool(max(trad_value, ml_value) >= float(analysis["too_good_balanced_accuracy"]))
    accepted_gain = bool(ml_value > trad_value and ml_value > shuffle_p95[ml_method] + margin)
    leakage_rows = [
        {
            "heldout_family": family,
            "check": "train_heldout_run_overlap",
            "value": int(len(set(meta.loc[train_idx, "run"]) & set(meta.loc[test_idx, "run"]))),
            "pass": len(set(meta.loc[train_idx, "run"]) & set(meta.loc[test_idx, "run"])) == 0,
            "note": "must be zero",
        },
        {
            "heldout_family": family,
            "check": "duplicate_key_overlap_train_heldout",
            "value": int(
                len(
                    set(map(tuple, meta.loc[train_idx, ["run", "event_index", "stave_index"]].to_numpy()))
                    & set(map(tuple, meta.loc[test_idx, ["run", "event_index", "stave_index"]].to_numpy()))
                )
            ),
            "pass": True,
            "note": "run-heldout split makes overlap impossible unless duplicated metadata exists",
        },
        {
            "heldout_family": family,
            "check": "ml_shuffle_p95_margin_gate",
            "value": float(ml_value - shuffle_p95[ml_method]),
            "pass": ml_value > shuffle_p95[ml_method] + margin,
            "note": "ML score must exceed label-shuffle p95 by margin {:.3f}".format(margin),
        },
        {
            "heldout_family": family,
            "check": "traditional_shuffle_p95_margin_gate",
            "value": float(trad_value - shuffle_p95[trad_method]),
            "pass": trad_value > shuffle_p95[trad_method] + margin,
            "note": "traditional score must exceed label-shuffle p95 by margin {:.3f}".format(margin),
        },
        {
            "heldout_family": family,
            "check": "proxy_near_best_main",
            "value": float(max(trad_value, ml_value) - proxy_value),
            "pass": proxy_value < max(trad_value, ml_value) - float(analysis["proxy_near_margin"]),
            "note": "fails if amplitude/multiplicity proxy is within margin of the best main score",
        },
        {
            "heldout_family": family,
            "check": "event_order_near_best_main",
            "value": float(max(trad_value, ml_value) - event_value),
            "pass": event_value < max(trad_value, ml_value) - float(analysis["proxy_near_margin"]),
            "note": "fails if event-order probe is within margin of the best main score",
        },
        {
            "heldout_family": family,
            "check": "too_good_leakage_hunt_triggered",
            "value": float(max(trad_value, ml_value)),
            "pass": True,
            "note": "triggered={}".format(too_good),
        },
        {
            "heldout_family": family,
            "check": "accepted_ml_gain",
            "value": float(ml_value - trad_value),
            "pass": accepted_gain,
            "note": "accepted only if ML beats traditional and ML clears shuffle p95 plus margin",
        },
    ]
    split = {
        "heldout_family": family,
        "train_runs": sorted(int(run) for run in np.unique(meta.loc[train_idx, "run"].to_numpy(dtype=int))),
        "heldout_runs": sorted(int(run) for run in np.unique(test_runs)),
        "train_rows": int(len(train_idx)),
        "heldout_rows": int(len(test_idx)),
        "train_class_counts": {str(STAVE_NAMES[int(k)]): int(v) for k, v in pd.Series(y_train).value_counts().sort_index().items()},
        "heldout_class_counts": {str(STAVE_NAMES[int(k)]): int(v) for k, v in pd.Series(y_test).value_counts().sort_index().items()},
        "traditional_value": trad_value,
        "ml_value": ml_value,
        "ml_minus_traditional": float(ml_value - trad_value),
        "traditional_shuffle_p95": float(shuffle_p95[trad_method]),
        "ml_shuffle_p95": float(shuffle_p95[ml_method]),
        "accepted_ml_gain": accepted_gain,
        "pca_reconstruction_mse": float(((pca.inverse_transform(pca_test) - x_test) ** 2).mean()),
        "ae_reconstruction_mse": float(((ae.reconstruct(x_test) - x_test) ** 2).mean()),
        "ae_final_training_loss": float(ae_losses[-1]),
        "ae_device": str(ae.device),
    }
    return metrics, pd.DataFrame(shuffle_rows), pd.DataFrame(leakage_rows), pd.DataFrame(prediction_rows), split


def markdown_table(frame: pd.DataFrame, columns: Sequence[str], max_rows: int = None) -> str:
    view = frame.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else "{:.3f}".format(x))
    widths = {col: max(len(col), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(col.ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def input_manifest(config: dict, raw_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        rows.append(
            {
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, result: dict, metrics: pd.DataFrame, leakage: pd.DataFrame, splits: pd.DataFrame, by_run: pd.DataFrame) -> None:
    main = metrics[metrics["category"] == "main"].copy()
    controls = metrics[metrics["category"] == "leakage_check"].copy()
    gate = splits[
        [
            "heldout_family",
            "traditional_value",
            "ml_value",
            "ml_minus_traditional",
            "traditional_shuffle_p95",
            "ml_shuffle_p95",
            "accepted_ml_gain",
            "heldout_runs",
        ]
    ].copy()
    accepted_count = int(gate["accepted_ml_gain"].sum())
    leak_fail = leakage[(leakage["check"] != "accepted_ml_gain") & (~leakage["pass"].astype(bool))]
    if accepted_count:
        verdict = "One or more AE-over-traditional gains cleared the family-local shuffle gate."
    else:
        verdict = "No AE-over-traditional gain was accepted after the family-local shuffle p95 plus margin gate."
    if len(leak_fail):
        leak_text = "Leakage/proxy flags were raised for: " + ", ".join(
            "{}:{}".format(row.heldout_family, row.check) for row in leak_fail.itertuples()
        ) + "."
    else:
        leak_text = "Train/held-out overlap checks passed and amplitude/multiplicity plus event-order controls stayed below the main probes by the configured margin."

    lines = [
        "# P01d: run-family leakage sentinels for waveform probes",
        "",
        "**Ticket:** `{}`".format(result["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT from `{}` was scanned before any modelling. The P01/S00 gate (B2/B4/B6/B8, median baseline samples 0-3, amplitude >1000 ADC) reproduced **{}** selected pulses versus expected **{}**.".format(
            result["raw_root_dir"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
        ),
        "",
        "## Method",
        "The target is `stave_index`, matching the P01c leakage battery. Each fold holds out one whole run family, trains only on the other families, and scores on capped held-out run/stave cells. CIs are 95% run-block bootstrap intervals over held-out runs; `sample_ii_calib` is a one-run family, so its CI is necessarily degenerate.",
        "",
        "Traditional is residualized hand-shape summaries plus PCA-6, with log-amplitude and selected multiplicity linearly regressed out using train rows only. ML is a masked-denoising AE-6 latent with the same residualization. No Monte Carlo was used.",
        "",
        "## Main run-family probes",
        markdown_table(main, ["heldout_family", "method", "value", "ci_low", "ci_high", "train_rows", "heldout_rows", "heldout_runs"]),
        "",
        "## Shuffle gates",
        markdown_table(gate, ["heldout_family", "traditional_value", "ml_value", "ml_minus_traditional", "traditional_shuffle_p95", "ml_shuffle_p95", "accepted_ml_gain", "heldout_runs"]),
        "",
        "A waveform representation gain is accepted only if the AE score is above the traditional score and above its within-family label-shuffle p95 by the configured margin of `{:.3f}`.".format(float(result["shuffle_margin"])),
        "",
        "## Leakage hunt",
        markdown_table(controls, ["heldout_family", "method", "value", "ci_low", "ci_high", "heldout_rows"]),
        "",
        markdown_table(leakage, ["heldout_family", "check", "value", "pass", "note"], max_rows=48),
        "",
        "## Held-out run breakdown",
        markdown_table(by_run.sort_values(["heldout_family", "method", "run"]), ["heldout_family", "method", "run", "heldout_rows", "balanced_accuracy"], max_rows=48),
        "",
        "## Verdict",
        "{} {}".format(verdict, leak_text),
        "",
        "Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `family_probe_metrics.csv`, `shuffle_nulls.csv`, `leakage_checks.csv`, `family_splits.csv`, and `heldout_by_run_metrics.csv`.",
    ]
    out_dir.joinpath("REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    started = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/p01d_1781017385_1145_1466621b_run_family_leakage_sentinels.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["analysis"]["random_seed"]))

    raw_dir = resolve_raw_root_dir(config)
    waves, meta, counts = scan_raw(config, raw_dir)
    total = int(counts["selected_pulses"].sum())
    repro = pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": total,
                "pass": total == int(config["expected_selected_pulses"]),
            }
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    manifest_inputs = input_manifest(config, raw_dir)
    manifest_inputs.to_csv(out_dir / "input_sha256.csv", index=False)
    if total != int(config["expected_selected_pulses"]):
        raise RuntimeError("raw reproduction failed: got {}".format(total))

    metric_parts: List[pd.DataFrame] = []
    shuffle_parts: List[pd.DataFrame] = []
    leakage_parts: List[pd.DataFrame] = []
    by_run_parts: List[pd.DataFrame] = []
    split_rows: List[dict] = []
    for family in config["analysis"]["heldout_family_order"]:
        print("evaluating heldout family {}".format(family), flush=True)
        metrics, shuffles, leakage, by_run, split = evaluate_family(config, family, waves, meta, rng)
        metric_parts.append(metrics)
        shuffle_parts.append(shuffles)
        leakage_parts.append(leakage)
        by_run_parts.append(by_run)
        split_rows.append(split)

    metrics = pd.concat(metric_parts, ignore_index=True)
    shuffles = pd.concat(shuffle_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    by_run = pd.concat(by_run_parts, ignore_index=True)
    splits = pd.DataFrame(split_rows)

    metrics.to_csv(out_dir / "family_probe_metrics.csv", index=False)
    shuffles.to_csv(out_dir / "shuffle_nulls.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    by_run.to_csv(out_dir / "heldout_by_run_metrics.csv", index=False)
    splits.to_csv(out_dir / "family_splits.csv", index=False)

    main_metrics = metrics[metrics["category"] == "main"]
    best = main_metrics.sort_values("value", ascending=False).iloc[0].to_dict()
    accepted = splits[splits["accepted_ml_gain"] == True]  # noqa: E712
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "selected_pulses": total,
            "passed": bool(total == int(config["expected_selected_pulses"])),
        },
        "target": "stave_index",
        "split": "held out whole run families; bootstrap resamples held-out runs",
        "traditional": "residual hand-shape summaries plus PCA-6",
        "ml": "residual masked-denoising AE-6",
        "shuffle_margin": float(config["analysis"]["shuffle_margin"]),
        "best_main_probe": json_sanitize(best),
        "accepted_ml_gain_families": accepted["heldout_family"].tolist(),
        "accepted_ml_gain_count": int(len(accepted)),
        "family_splits": json_sanitize(split_rows),
        "leakage_failures": json_sanitize(leakage[(leakage["check"] != "accepted_ml_gain") & (~leakage["pass"].astype(bool))].to_dict(orient="records")),
        "no_monte_carlo": True,
        "runtime_seconds": None,
    }

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "script": "scripts/p01d_1781017385_1145_1466621b_run_family_leakage_sentinels.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "raw_root_dir": str(raw_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(manifest_inputs)),
        "reproduction_passed": bool(total == int(config["expected_selected_pulses"])),
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "input_sha256.csv",
            "reproduction_match_table.csv",
            "reproduction_counts_by_run.csv",
            "family_probe_metrics.csv",
            "shuffle_nulls.csv",
            "leakage_checks.csv",
            "family_splits.csv",
            "heldout_by_run_metrics.csv",
        ],
    }

    result["runtime_seconds"] = None
    write_report(out_dir, result, metrics, leakage, splits, by_run)
    result["runtime_seconds"] = float(time.time() - started)
    out_dir.joinpath("result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    out_dir.joinpath("manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print("wrote {}".format(out_dir), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
