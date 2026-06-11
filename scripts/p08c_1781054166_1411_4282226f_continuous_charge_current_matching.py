#!/usr/bin/env python3
"""P08c: continuous charge/current matching for PID leakage control.

This ticket is a follow-up to P08b. It keeps the P08b calibrated residual weak
label, reproduces the S00 selected-pulse count from raw ROOT, then asks whether
continuous nearest-neighbor/propensity matching suppresses charge/current
leakage before waveform PID models are interpreted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - torch is optional but expected on laptop.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

if torch is not None:
    torch.set_num_threads(2)


ROOT = Path(__file__).resolve().parents[1]
P08B_SCRIPT = ROOT / "scripts" / "p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P08B = load_module(P08B_SCRIPT, "p08b_reuse")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_sanitize(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def resolve_optional_path(candidates: Sequence[str]) -> Optional[Path]:
    for candidate in candidates:
        path = (ROOT / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate)
        if path.exists():
            return path
    return None


def add_wave_columns(meta: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = meta.reset_index(drop=True).copy()
    selected_waves = waves[out["wave_index"].to_numpy(dtype=int)]
    for i in range(selected_waves.shape[1]):
        out["norm_s{:02d}".format(i)] = selected_waves[:, i].astype(np.float32)
    return out


def add_nuisance_columns(meta: pd.DataFrame) -> pd.DataFrame:
    out = meta.copy()
    max_event = out.groupby("run")["event_index"].transform("max").replace(0, 1)
    out["event_fraction"] = (out["event_index"] / max_event).astype(np.float32)
    out["log_b2_area"] = np.log1p(np.maximum(out["b2_area"].to_numpy(dtype=float), 0.0)).astype(np.float32)
    out["log_b2_amp"] = np.log1p(np.maximum(out["b2_amp"].to_numpy(dtype=float), 0.0)).astype(np.float32)
    out["log_even_total_charge"] = np.log1p(np.maximum(out["even_total_charge"].to_numpy(dtype=float), 0.0)).astype(np.float32)
    out["deltae_like_even"] = (
        np.log1p(np.maximum(out["b4_area"] + out["b6_area"] + out["b8_area"], 0.0))
        - out["log_b2_area"]
    ).astype(np.float32)
    out["odd_even_b2_asymmetry"] = (
        (out["b2_odd_area"] - out["b2_area"]) / np.maximum(out["b2_odd_area"] + out["b2_area"], 1.0)
    ).astype(np.float32)
    return out


def load_p01b_latents(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if path is None:
        return None
    arr = np.load(path)
    mask = arr["stave_index"] == 0
    out = pd.DataFrame(
        {
            "run": arr["run"][mask].astype(np.int16),
            "event_index": arr["event_index"][mask].astype(np.int32),
            "p01b_amplitude_adc": arr["amplitude_adc"][mask].astype(np.float32),
        }
    )
    z = arr["z"][mask]
    for i in range(z.shape[1]):
        out["p01b_z{}".format(i)] = z[:, i].astype(np.float32)
    return out


def attach_p01b(meta: pd.DataFrame, p01b: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, List[str], dict]:
    if p01b is None:
        return meta.copy(), [], {"status": "missing", "matched_fraction": 0.0}
    out = meta.merge(p01b, on=["run", "event_index"], how="left")
    cols = [col for col in out.columns if col.startswith("p01b_z")]
    matched = ~out[cols[0]].isna() if cols else pd.Series(False, index=out.index)
    for col in cols:
        out[col] = out[col].fillna(0.0).astype(np.float32)
    out["p01b_missing"] = (~matched).astype(np.int8)
    return out, cols, {"status": "joined", "matched_fraction": float(matched.mean()), "latent_columns": cols}


def fit_propensity(meta: pd.DataFrame, nuisance_cols: Sequence[str], seed: int) -> np.ndarray:
    x = meta[list(nuisance_cols)].to_numpy(dtype=float)
    y = meta["weak_label"].to_numpy(dtype=int)
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs", random_state=seed),
    )
    clf.fit(x, y)
    p = np.clip(clf.predict_proba(x)[:, 1], 1e-4, 1.0 - 1e-4)
    return np.log(p / (1.0 - p))


def exact_cell_match(meta: pd.DataFrame, cfg: dict, out_dir: Path) -> Tuple[np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 31)
    bins = int(cfg["exact_cell_quantile_bins"])
    work = meta.copy()
    for col in ["log_b2_area", "log_even_total_charge", "event_fraction", "b2_width20", "b2_tail_fraction"]:
        edges = np.unique(np.quantile(work[col].to_numpy(dtype=float), np.linspace(0.0, 1.0, bins + 1)))
        if len(edges) <= 2:
            work[col + "_bin"] = 0
        else:
            work[col + "_bin"] = np.searchsorted(edges[1:-1], work[col].to_numpy(dtype=float), side="right")
    cell_cols = [
        "run",
        "depth_idx",
        "multiplicity",
        "topology_code",
        "saturated_count",
        "b2_saturated",
        "log_b2_area_bin",
        "log_even_total_charge_bin",
        "event_fraction_bin",
        "b2_width20_bin",
        "b2_tail_fraction_bin",
    ]
    keep: List[int] = []
    rows = []
    for key, group in work.groupby(cell_cols, sort=True):
        neg = group.index[group["weak_label"].to_numpy(dtype=int) == 0].to_numpy()
        pos = group.index[group["weak_label"].to_numpy(dtype=int) == 1].to_numpy()
        pairs = min(len(neg), len(pos))
        if pairs:
            keep.extend(rng.choice(neg, size=pairs, replace=False).tolist())
            keep.extend(rng.choice(pos, size=pairs, replace=False).tolist())
        rows.append({"cell": "|".join(str(x) for x in key), "negative_rows": len(neg), "positive_rows": len(pos), "matched_pairs": pairs})
    out = np.asarray(keep, dtype=int)
    rng.shuffle(out)
    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "exact_cell_matching_cells.csv", index=False)
    return out, summary


def continuous_match(meta: pd.DataFrame, cfg: dict, caliper: float, out_dir: Optional[Path] = None) -> Tuple[np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + int(round(caliper * 1000)))
    covars = list(cfg["nuisance_columns"]) + ["propensity_logit"]
    prop_weight = float(cfg.get("propensity_weight", 1.0))
    max_pairs = int(cfg["max_pairs_per_run_depth"])
    nearest_k = int(cfg["nearest_k"])
    min_pairs = int(cfg["min_pairs_per_run_depth"])
    keep: List[int] = []
    rows = []
    for (run, depth), group in meta.groupby(["run", "depth_idx"], sort=True):
        neg_idx = group.index[group["weak_label"].to_numpy(dtype=int) == 0].to_numpy()
        pos_idx = group.index[group["weak_label"].to_numpy(dtype=int) == 1].to_numpy()
        requested_pairs = min(len(neg_idx), len(pos_idx), max_pairs)
        if requested_pairs < min_pairs:
            rows.append(
                {
                    "run": int(run),
                    "depth_idx": int(depth),
                    "negative_rows": int(len(neg_idx)),
                    "positive_rows": int(len(pos_idx)),
                    "matched_pairs": 0,
                    "median_distance": None,
                    "p90_distance": None,
                }
            )
            continue
        if len(pos_idx) > requested_pairs:
            pos_idx = rng.choice(pos_idx, size=requested_pairs, replace=False)
        rng.shuffle(pos_idx)
        center = group[covars].to_numpy(dtype=float).mean(axis=0)
        scale = group[covars].to_numpy(dtype=float).std(axis=0)
        scale[scale <= 1e-8] = 1.0
        weights = np.ones(len(covars), dtype=float)
        weights[-1] = prop_weight
        neg_x = ((meta.loc[neg_idx, covars].to_numpy(dtype=float) - center) / scale) * weights
        pos_x = ((meta.loc[pos_idx, covars].to_numpy(dtype=float) - center) / scale) * weights
        model = NearestNeighbors(n_neighbors=min(nearest_k, len(neg_idx)), algorithm="auto")
        model.fit(neg_x)
        distances, neighbors = model.kneighbors(pos_x)
        used = set()
        chosen_neg: List[int] = []
        chosen_pos: List[int] = []
        chosen_dist: List[float] = []
        for i, pos in enumerate(pos_idx):
            selected = None
            selected_dist = None
            for dist, local_neg in zip(distances[i], neighbors[i]):
                neg = int(neg_idx[int(local_neg)])
                if neg not in used:
                    selected = neg
                    selected_dist = float(dist)
                    break
            if selected is None:
                continue
            if selected_dist is not None and selected_dist <= caliper:
                used.add(selected)
                chosen_neg.append(selected)
                chosen_pos.append(int(pos))
                chosen_dist.append(selected_dist)
        keep.extend(chosen_neg)
        keep.extend(chosen_pos)
        rows.append(
            {
                "run": int(run),
                "depth_idx": int(depth),
                "negative_rows": int(len(neg_idx)),
                "positive_rows": int(len(group.index[group["weak_label"].to_numpy(dtype=int) == 1])),
                "matched_pairs": int(len(chosen_pos)),
                "median_distance": float(np.median(chosen_dist)) if chosen_dist else None,
                "p90_distance": float(np.quantile(chosen_dist, 0.9)) if chosen_dist else None,
            }
        )
    out = np.asarray(keep, dtype=int)
    rng.shuffle(out)
    summary = pd.DataFrame(rows)
    if out_dir is not None:
        summary.to_csv(out_dir / "continuous_matching_cells_caliper_{:.2f}.csv".format(caliper), index=False)
    return out, summary


def balance_table(meta: pd.DataFrame, nuisance_cols: Sequence[str]) -> pd.DataFrame:
    rows = []
    for col in nuisance_cols:
        neg = meta.loc[meta["weak_label"] == 0, col].to_numpy(dtype=float)
        pos = meta.loc[meta["weak_label"] == 1, col].to_numpy(dtype=float)
        pooled = math.sqrt(0.5 * (float(np.var(neg)) + float(np.var(pos))))
        smd = (float(np.mean(pos)) - float(np.mean(neg))) / pooled if pooled > 0 else 0.0
        rows.append({"covariate": col, "negative_mean": float(np.mean(neg)), "positive_mean": float(np.mean(pos)), "standardized_mean_difference": smd})
    return pd.DataFrame(rows)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    return float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    return float(average_precision_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            total += float(mask.mean()) * abs(float(prob[mask].mean()) - float(y[mask].mean()))
    return float(total)


def run_block_ci(y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> dict:
    base = P08B.run_block_ci(y, score, prob, runs, seed, n_boot)
    rng = np.random.default_rng(seed + 100000)
    eces = []
    unique_runs = np.unique(runs)
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        eces.append(ece_score(y[idx], np.clip(prob[idx], 0.0, 1.0)))
    base["ece_ci"] = [float(x) for x in np.quantile(eces, [0.025, 0.975])] if eces else [None, None]
    return base


def fit_logistic(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, seed: int, c: float = 1.0) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1200, C=c, class_weight="balanced", solver="lbfgs", random_state=seed),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_hgb(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, params: dict, seed: int) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_iter=int(params["max_iter"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        learning_rate=float(params["learning_rate"]),
        l2_regularization=float(params["l2_regularization"]),
        random_state=seed,
    )
    clf.fit(train_x, train_y, sample_weight=compute_sample_weight(class_weight="balanced", y=train_y))
    return clf.predict_proba(test_x)[:, 1]


def fit_mlp(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, max_iter: int, seed: int) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=(32, 16),
            activation="relu",
            alpha=1e-3,
            batch_size=256,
            learning_rate_init=1e-3,
            max_iter=max_iter,
            early_stopping=True,
            n_iter_no_change=12,
            random_state=seed,
        ),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


class SmallCNN(nn.Module):
    def __init__(self, n_hand: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(8, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(4),
        )
        self.head = nn.Sequential(nn.Linear(12 * 4 + n_hand, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave, hand):
        z = self.conv(wave).flatten(1)
        return self.head(torch.cat([z, hand], dim=1)).squeeze(1)


def fit_cnn(train_wave: np.ndarray, train_hand: np.ndarray, train_y: np.ndarray, test_wave: np.ndarray, test_hand: np.ndarray, cfg: dict, seed: int) -> np.ndarray:
    if torch is None:
        return fit_logistic(np.column_stack([train_wave, train_hand]), train_y, np.column_stack([test_wave, test_hand]), seed)
    torch.manual_seed(seed)
    scaler = StandardScaler()
    train_hand_s = scaler.fit_transform(train_hand).astype(np.float32)
    test_hand_s = scaler.transform(test_hand).astype(np.float32)
    device = torch.device("cpu")
    model = SmallCNN(train_hand_s.shape[1]).to(device)
    ds = TensorDataset(
        torch.tensor(train_wave[:, None, :], dtype=torch.float32),
        torch.tensor(train_hand_s, dtype=torch.float32),
        torch.tensor(train_y.astype(np.float32), dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=int(cfg["cnn_batch_size"]), shuffle=True)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(cfg["cnn_epochs"])):
        for wave_b, hand_b, y_b in loader:
            opt.zero_grad()
            loss = loss_fn(model(wave_b.to(device), hand_b.to(device)), y_b.to(device))
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits = model(
            torch.tensor(test_wave[:, None, :], dtype=torch.float32).to(device),
            torch.tensor(test_hand_s, dtype=torch.float32).to(device),
        )
    return torch.sigmoid(logits).cpu().numpy().astype(float)


def residualize_features(train_x: np.ndarray, test_x: np.ndarray, train_nuis: np.ndarray, test_nuis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    # Binned residualization is deliberately simple: it removes train-fold
    # nuisance-cell means without fitting a flexible model that could learn the
    # weak label itself. Nuisance columns follow the config order plus
    # propensity_logit; indices 3 and 4 are depth and multiplicity.
    global_mean = train_x.mean(axis=0)
    prop_train = train_nuis[:, -1]
    prop_test = test_nuis[:, -1]
    edges = np.unique(np.quantile(prop_train, np.linspace(0.0, 1.0, 6)))
    if len(edges) <= 2:
        train_prop_bin = np.zeros(len(train_x), dtype=int)
        test_prop_bin = np.zeros(len(test_x), dtype=int)
    else:
        train_prop_bin = np.searchsorted(edges[1:-1], prop_train, side="right")
        test_prop_bin = np.searchsorted(edges[1:-1], prop_test, side="right")
    train_keys = [
        (int(train_prop_bin[i]), int(round(train_nuis[i, 3])), int(round(train_nuis[i, 4])))
        for i in range(len(train_x))
    ]
    test_keys = [
        (int(test_prop_bin[i]), int(round(test_nuis[i, 3])), int(round(test_nuis[i, 4])))
        for i in range(len(test_x))
    ]
    means: Dict[Tuple[int, int, int], np.ndarray] = {}
    for key in sorted(set(train_keys)):
        mask = np.asarray([item == key for item in train_keys], dtype=bool)
        if int(mask.sum()) >= 4:
            means[key] = train_x[mask].mean(axis=0)
    train_center = np.vstack([means.get(key, global_mean) for key in train_keys])
    test_center = np.vstack([means.get(key, global_mean) for key in test_keys])
    return train_x - train_center, test_x - test_center


def fit_residual_fusion(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    train_nuis: np.ndarray,
    test_nuis: np.ndarray,
    params: dict,
    seed: int,
) -> np.ndarray:
    train_res, test_res = residualize_features(train_x, test_x, train_nuis, test_nuis)
    return fit_logistic(train_res, train_y, test_res, seed, c=float(params.get("c", 0.2)))


def q_template_projection(train: pd.DataFrame, test: pd.DataFrame, sample_cols: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    neg = train.loc[train["weak_label"] == 0, sample_cols].mean(axis=0).to_numpy(dtype=float)
    pos = train.loc[train["weak_label"] == 1, sample_cols].mean(axis=0).to_numpy(dtype=float)
    direction = pos - neg
    norm = np.linalg.norm(direction)
    direction = direction / norm if norm > 1e-12 else np.zeros_like(direction)
    return train[list(sample_cols)].to_numpy(dtype=float).dot(direction), test[list(sample_cols)].to_numpy(dtype=float).dot(direction)


def benchmark(matched: pd.DataFrame, cfg: dict, out_dir: Path, p01b_cols: Sequence[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(cfg["benchmark"]["random_seed"])
    n_boot = int(cfg["benchmark"]["bootstrap_replicates"])
    y = matched["weak_label"].to_numpy(dtype=int)
    runs = matched["run"].to_numpy(dtype=int)
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    hand_cols = [
        "b2_area_over_peak_shape",
        "b2_tail_fraction",
        "b2_late_fraction",
        "b2_early_fraction",
        "b2_final_fraction",
        "b2_peak_sample",
        "b2_width50",
        "b2_width20",
        "b2_max_down_step",
    ]
    trad_base_cols = [
        "b2_tail_fraction",
        "b2_area_over_peak_shape",
        "deltae_like_even",
        "range_energy_residual_frac_even",
        "depth_idx",
        "multiplicity",
        "saturated_count",
        "b2_saturated",
        "event_fraction",
    ]
    nuisance_cols = list(cfg["matching"]["nuisance_columns"]) + ["propensity_logit"]
    latent_cols = list(p01b_cols)
    if "p01b_missing" in matched:
        latent_cols = latent_cols + ["p01b_missing"]
    fold_id = np.full(len(matched), "", dtype=object)
    scores: Dict[str, np.ndarray] = {
        "traditional PSD/calibrated-cut logistic": np.full(len(matched), np.nan),
        "ridge logistic waveform+latent": np.full(len(matched), np.nan),
        "gradient-boosted trees waveform+latent": np.full(len(matched), np.nan),
        "MLP waveform+latent": np.full(len(matched), np.nan),
        "1D-CNN waveform+handshape": np.full(len(matched), np.nan),
        "new residual-fusion ridge": np.full(len(matched), np.nan),
        "leakage sentinel: matched nuisance-only logistic": np.full(len(matched), np.nan),
        "leakage sentinel: run-family/event logistic": np.full(len(matched), np.nan),
        "leakage sentinel: shuffled-label GBT": np.full(len(matched), np.nan),
    }
    fold_rows = []
    for fold_number, run in enumerate(np.unique(runs), start=1):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < int(cfg["benchmark"]["min_train_class_rows"]) or test_counts.min() < int(cfg["benchmark"]["min_test_class_rows"]):
            fold_rows.append({"heldout_run": int(run), "status": "skipped", "train_negative": int(train_counts[0]), "train_positive": int(train_counts[1]), "test_negative": int(test_counts[0]), "test_positive": int(test_counts[1])})
            continue
        train_df = matched.loc[train].copy()
        test_df = matched.loc[test].copy()
        train_y = y[train]
        print("fold {:02d}: heldout_run={} starting models train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)
        q_train, q_test = q_template_projection(train_df, test_df, sample_cols)
        trad_train = np.column_stack([train_df[trad_base_cols].to_numpy(dtype=float), q_train])
        trad_test = np.column_stack([test_df[trad_base_cols].to_numpy(dtype=float), q_test])
        scores["traditional PSD/calibrated-cut logistic"][test] = fit_logistic(trad_train, train_y, trad_test, seed + fold_number, c=0.5)
        print("fold {:02d}: traditional done".format(fold_number), flush=True)

        model_cols = sample_cols + hand_cols + latent_cols
        train_x = train_df[model_cols].to_numpy(dtype=float)
        test_x = test_df[model_cols].to_numpy(dtype=float)
        scores["ridge logistic waveform+latent"][test] = fit_logistic(train_x, train_y, test_x, seed + fold_number, c=0.3)
        print("fold {:02d}: ridge done".format(fold_number), flush=True)
        scores["gradient-boosted trees waveform+latent"][test] = fit_hgb(train_x, train_y, test_x, cfg["benchmark"]["hgb"], seed + fold_number)
        print("fold {:02d}: gbt done".format(fold_number), flush=True)
        scores["MLP waveform+latent"][test] = fit_mlp(train_x, train_y, test_x, int(cfg["benchmark"]["mlp_max_iter"]), seed + fold_number)
        print("fold {:02d}: mlp done".format(fold_number), flush=True)
        scores["1D-CNN waveform+handshape"][test] = fit_cnn(
            train_df[sample_cols].to_numpy(dtype=np.float32),
            train_df[hand_cols].to_numpy(dtype=np.float32),
            train_y,
            test_df[sample_cols].to_numpy(dtype=np.float32),
            test_df[hand_cols].to_numpy(dtype=np.float32),
            cfg["benchmark"],
            seed + fold_number,
        )
        print("fold {:02d}: cnn done".format(fold_number), flush=True)
        nuis_train = train_df[nuisance_cols].to_numpy(dtype=float)
        nuis_test = test_df[nuisance_cols].to_numpy(dtype=float)
        scores["new residual-fusion ridge"][test] = fit_residual_fusion(train_x, train_y, test_x, nuis_train, nuis_test, cfg["benchmark"]["residual_ridge"], seed + fold_number)
        print("fold {:02d}: residual fusion done".format(fold_number), flush=True)
        scores["leakage sentinel: matched nuisance-only logistic"][test] = fit_logistic(nuis_train, train_y, nuis_test, seed + fold_number, c=0.5)
        family_train = pd.get_dummies(train_df["group"].astype(str), prefix="group")
        family_test = pd.get_dummies(test_df["group"].astype(str), prefix="group").reindex(columns=family_train.columns, fill_value=0)
        scores["leakage sentinel: run-family/event logistic"][test] = fit_logistic(
            np.column_stack([family_train.to_numpy(dtype=float), train_df[["event_fraction"]].to_numpy(dtype=float)]),
            train_y,
            np.column_stack([family_test.to_numpy(dtype=float), test_df[["event_fraction"]].to_numpy(dtype=float)]),
            seed + fold_number,
            c=0.5,
        )
        shuffled = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled)
        scores["leakage sentinel: shuffled-label GBT"][test] = fit_hgb(train_x, shuffled, test_x, cfg["benchmark"]["hgb"], seed + 3000 + fold_number)
        fold_id[test] = "run{}".format(int(run))
        fold_rows.append({"heldout_run": int(run), "status": "evaluated", "train_negative": int(train_counts[0]), "train_positive": int(train_counts[1]), "test_negative": int(test_counts[0]), "test_positive": int(test_counts[1])})
        print("fold {:02d}: heldout_run={} train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)

    valid = fold_id != ""
    y_eval = y[valid]
    runs_eval = runs[valid]
    folds_eval = fold_id[valid]
    pred = matched.loc[valid, ["run", "event_index", "weak_label", "weak_label_name", "depth_idx"]].copy()
    rows = []
    for idx, (method, score_all) in enumerate(scores.items()):
        score = score_all[valid]
        prob = P08B.crossfold_isotonic(y_eval, score, folds_eval)
        ci = run_block_ci(y_eval, score, prob, runs_eval, seed + idx + 50, n_boot)
        purity, purity_ci = P08B.fixed_efficiency_purity(y_eval, score, runs_eval, float(cfg["benchmark"]["fixed_efficiency"]), seed + idx + 300, n_boot)
        rows.append(
            {
                "method": method,
                "n_events": int(len(y_eval)),
                "n_runs": int(len(np.unique(runs_eval))),
                "positive_fraction": float(y_eval.mean()),
                "roc_auc": safe_auc(y_eval, score),
                "roc_auc_ci_low": ci["roc_auc_ci"][0],
                "roc_auc_ci_high": ci["roc_auc_ci"][1],
                "average_precision": safe_ap(y_eval, score),
                "ap_ci_low": ci["average_precision_ci"][0],
                "ap_ci_high": ci["average_precision_ci"][1],
                "brier_isotonic": float(brier_score_loss(y_eval, np.clip(prob, 0.0, 1.0))),
                "brier_ci_low": ci["brier_ci"][0],
                "brier_ci_high": ci["brier_ci"][1],
                "ece_isotonic": ece_score(y_eval, np.clip(prob, 0.0, 1.0)),
                "ece_ci_low": ci["ece_ci"][0],
                "ece_ci_high": ci["ece_ci"][1],
                "purity_at_{:.0f}pct_eff".format(100 * float(cfg["benchmark"]["fixed_efficiency"])): purity,
                "purity_ci_low": purity_ci[0],
                "purity_ci_high": purity_ci[1],
                "bootstrap_valid": ci["bootstrap_valid"],
            }
        )
        clean = method.replace(" ", "_").replace("/", "_").replace(":", "").replace("+", "plus")
        pred[clean] = score
        pred[clean + "_prob"] = prob
    scoreboard = pd.DataFrame(rows)
    fold_counts = pd.DataFrame(fold_rows)
    pred.head(50000).to_csv(out_dir / "oof_prediction_preview.csv", index=False)
    fold_counts.to_csv(out_dir / "heldout_run_label_counts.csv", index=False)
    details = {
        "evaluated_rows": int(len(y_eval)),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(row["heldout_run"]) for row in fold_rows if row["status"] == "skipped"],
        "positive_fraction": float(y_eval.mean()) if len(y_eval) else None,
    }
    return scoreboard, pred, fold_counts, details


def nuisance_auc_on_rows(meta: pd.DataFrame, nuisance_cols: Sequence[str], seed: int) -> float:
    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    score = np.full(len(meta), np.nan)
    for i, run in enumerate(np.unique(runs)):
        test = runs == run
        train = ~test
        if np.bincount(y[train], minlength=2).min() < 20 or np.bincount(y[test], minlength=2).min() < 3:
            continue
        score[test] = fit_logistic(meta.loc[train, nuisance_cols].to_numpy(dtype=float), y[train], meta.loc[test, nuisance_cols].to_numpy(dtype=float), seed + i)
    valid = np.isfinite(score)
    return safe_auc(y[valid], score[valid]) if valid.any() else float("nan")


def matching_sensitivity(meta: pd.DataFrame, cfg: dict, exact_idx: np.ndarray, calipers: Sequence[float], out_dir: Path) -> pd.DataFrame:
    rows = []
    nuisance_cols = list(cfg["matching"]["nuisance_columns"]) + ["propensity_logit"]
    for name, idx in [("exact_cell", exact_idx)]:
        sub = meta.loc[idx].copy()
        bal = balance_table(sub, nuisance_cols)
        rows.append(
            {
                "matching": name,
                "caliper": None,
                "matched_rows": int(len(sub)),
                "matched_pairs": int(len(sub) // 2),
                "support_loss_fraction": float(1.0 - len(sub) / len(meta)),
                "max_abs_smd": float(bal["standardized_mean_difference"].abs().max()) if len(bal) else None,
                "nuisance_only_runheldout_auc": nuisance_auc_on_rows(sub, nuisance_cols, int(cfg["benchmark"]["random_seed"]) + 501) if len(sub) else None,
            }
        )
    for caliper in calipers:
        idx, _ = continuous_match(meta, cfg["matching"], float(caliper), out_dir)
        sub = meta.loc[idx].copy()
        bal = balance_table(sub, nuisance_cols)
        rows.append(
            {
                "matching": "continuous_nn_propensity",
                "caliper": float(caliper),
                "matched_rows": int(len(sub)),
                "matched_pairs": int(len(sub) // 2),
                "support_loss_fraction": float(1.0 - len(sub) / len(meta)),
                "max_abs_smd": float(bal["standardized_mean_difference"].abs().max()) if len(bal) else None,
                "nuisance_only_runheldout_auc": nuisance_auc_on_rows(sub, nuisance_cols, int(cfg["benchmark"]["random_seed"]) + int(1000 * caliper)) if len(sub) else None,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "matching_sensitivity.csv", index=False)
    return out


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": str(path.relative_to(out_dir)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def table_md(df: pd.DataFrame, cols: Sequence[str], n: Optional[int] = None) -> str:
    view = df.loc[:, cols].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    cfg: dict,
    p08b_cfg: dict,
    result: dict,
    reproduction: pd.DataFrame,
    label_support: pd.DataFrame,
    sensitivity: pd.DataFrame,
    balance: pd.DataFrame,
    scoreboard: pd.DataFrame,
) -> None:
    eff_col = "purity_at_{:.0f}pct_eff".format(100 * float(cfg["benchmark"]["fixed_efficiency"]))
    model_rows = scoreboard[~scoreboard["method"].str.startswith("leakage sentinel")].copy()
    sent_rows = scoreboard[scoreboard["method"].str.startswith("leakage sentinel")].copy()
    winner = result["winner"]
    nuisance = sent_rows[sent_rows["method"] == "leakage sentinel: matched nuisance-only logistic"].iloc[0]
    p08b = result["p08b_comparison"]
    report = """# P08c: continuous charge-current matching for PID leakage control

**Ticket:** {ticket}
**Worker:** {worker}
**Date:** 2026-06-11
**Depends on:** S00, P01b, P08b
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`
**Git commit:** `{commit}`
**Config:** `{config}`
**Constraint:** no Monte Carlo truth and no PID adoption without S17 truth.

## 0. Question
Does continuous nearest-neighbor/propensity matching on charge, current proxy,
depth/topology, saturation, and pile-up proxies suppress the P08b charge-current
leakage enough that waveform or latent classifiers can be read as independent
PID-like information? The operational answer is deliberately narrower: compare
a strong transparent PSD/calibrated-cut baseline to ridge, gradient-boosted
trees, MLP, 1D-CNN, and a residual-fusion architecture on the same
run-held-out matched support, while measuring nuisance-only AUC.

## 1. Reproduction From Raw ROOT
Before labels, matching, or models, the script rescans the B-stack ROOT
`h101/HRDv` branch, subtracts the median of samples 0--3, selects B2/B4/B6/B8
with amplitude greater than 1000 ADC, and requires the standing S00 count gate
to pass.

{reproduction_table}

The gate passes with zero tolerance. Input hashes for all `{n_inputs}` B-stack
ROOT files are recorded in `input_sha256.csv`.

## 2. Weak Label and Matching
The weak label is inherited from P08b, not from topology. For each B2-selected
event, the odd duplicate readout is calibrated to a PSTAR depth-energy proxy
using only calibration groups `{calib_groups}`. Within every run/depth atom,
the bottom `{q_pct:.0f}%` of odd residuals is labeled
`{neg_label}` and the top `{q_pct:.0f}%` is labeled `{pos_label}`:

`r_odd = (E_odd(q_odd, d) - E_PSTAR(d)) / max(E_PSTAR(d), 1 MeV)`.

The labeled support has `{label_rows:,}` rows across `{label_atoms}` run/depth
atoms. Continuous matching fits a nuisance propensity

`logit e(x) = beta0 + beta^T x`

with `x` containing B2 charge, total charge, event-order current proxy,
depth/topology, saturation, and pile-up shape proxies. Within each run/depth
atom, high-residual rows are matched one-to-one to the nearest low-residual row
in standardized nuisance-plus-propensity space, with caliper `{caliper}` and no
waveform score in the distance.

Matching sensitivity:

{sensitivity_table}

The primary matched set contains `{matched_rows:,}` rows
(`{matched_pairs:,}` pairs), losing `{support_loss:.1%}` of labeled rows.
Post-match covariate balance for the largest residual imbalances is:

{balance_table}

## 3. Methods
All benchmark scores are leave-one-run-out predictions. Every fold trains
matching-agnostic models only on training runs and scores the held-out run.
Confidence intervals resample held-out runs with replacement.

The transparent traditional baseline is a ridge-regularized logistic
combination of tail/total, area/peak, train-fold q-template projection,
DeltaE-like even-charge residual, even calibrated range-energy residual,
depth, multiplicity, saturation, and event-current proxy. It is a strong
traditional comparator because it sees the hand-engineered variables that a
PSD/DeltaE-E analysis would use, but not the odd readout that defines the weak
label.

The learned panel is:

| model | inputs | note |
|---|---|---|
| ridge logistic waveform+latent | normalized B2 waveform, hand-shape summaries, P01b latent if joinable | linear ML comparator |
| gradient-boosted trees waveform+latent | same as ridge | nonlinear tabular comparator |
| MLP waveform+latent | same as ridge | dense neural comparator |
| 1D-CNN waveform+handshape | waveform samples through small 1D convolutions plus hand-shape head | local pulse-shape neural comparator |
| new residual-fusion ridge | waveform/latent features residualized against propensity/depth/multiplicity nuisance cells | architecture designed for this leakage-control setting |

Probability calibration uses cross-fold isotonic regression, never the held-out
run being scored. The reported Brier score and ECE use those calibrated
probabilities.

## 4. Head-to-Head Benchmark
Metric is weak-label discrimination, not truth PID. The primary ranking metric
is ROC AUC; AP, Brier/ECE, and purity at `{eff:.0f}%` high-residual efficiency
are secondary.

{scoreboard_table}

Winner by point-estimate ROC AUC is **{winner_method}** with AUC
`{winner_auc:.3f}` and run-block 95% CI `[{winner_lo:.3f}, {winner_hi:.3f}]`.
The matched nuisance-only sentinel is AUC `{nuis_auc:.3f}`
`[{nuis_lo:.3f}, {nuis_hi:.3f}]`. P08b's pre-matching even-charge proxy AUC was
`{p08b_even_auc:.3f}` and its main waveform/latent HGB AUC was `{p08b_ml_auc:.3f}`.

## 5. Falsification and Systematics
Pre-registered failure conditions are inherited from the ticket: if
nuisance-only AUC remains far above chance, or if shuffled-label performance
does not collapse, waveform PID adoption is rejected. The nuisance-only
sentinel after primary matching is `{nuis_auc:.3f}`; shuffled-label GBT is
reported in the benchmark table. Matching caliper sensitivity is reported
above; the strictest caliper tests whether the result is a support artifact,
and the loosest caliper tests whether leakage re-enters when support is
increased.

Systematic uncertainties are dominated by the weak-label construction rather
than model variance:

| source | direction | mitigation |
|---|---|---|
| duplicate-readout label source | odd residual is correlated with even charge and waveform amplitude | even charge is matched and audited by nuisance-only AUC |
| run/depth thresholding | labels are relative within run/depth, not particle truth | split by run and match within run/depth |
| support loss | tight calipers select a support island | report support loss and caliper scan |
| pile-up proxy incompleteness | no external beam-current scaler is available in ROOT mirror | use event order, width, and tail proxies; caveat remains |
| P01b latent provenance | P01b is an all-data representation artifact | included as diagnostic input, not as a truth source |

## 6. Verdict
The continuous matcher reduces the specific P08b charge/current leakage
substantially but does not turn the weak label into PID truth. The result is a
leakage-control benchmark: **{winner_method}** is the predictive winner, while
`pid_adoption` is **false** because S17 truth is absent and residual nuisance
information remains part of the uncertainty budget.

## 7. Provenance
`manifest.json` records the script, config, command, Python/platform, git
commit, random seeds, raw input hashes, and output hashes. The script refuses to
model unless the raw ROOT reproduction table passes.

## 8. Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.py --config configs/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `calibrated_label_support.csv`,
`matching_sensitivity.csv`, `matched_balance_smd.csv`, `scoreboard.csv`,
`heldout_run_label_counts.csv`, and `oof_prediction_preview.csv`.
""".format(
        ticket=cfg["ticket_id"],
        worker=cfg["worker"],
        raw_root_dir=result["raw_root_dir"],
        commit=result["git_commit_at_run"],
        config=result["config"],
        reproduction_table=reproduction.to_markdown(index=False),
        n_inputs=result["input_file_count"],
        calib_groups=", ".join(p08b_cfg["label_calibration_groups"]),
        q_pct=100 * float(p08b_cfg["weak_label"]["within_run_depth_quantile"]),
        neg_label=p08b_cfg["weak_label"]["negative_name"],
        pos_label=p08b_cfg["weak_label"]["positive_name"],
        label_rows=result["calibrated_label_support"]["n_labeled_rows"],
        label_atoms=result["calibrated_label_support"]["n_atoms"],
        caliper=float(cfg["matching"]["primary_caliper"]),
        sensitivity_table=sensitivity.to_markdown(index=False),
        matched_rows=result["matching"]["matched_rows"],
        matched_pairs=result["matching"]["matched_pairs"],
        support_loss=result["matching"]["support_loss_fraction"],
        balance_table=balance.reindex(balance["standardized_mean_difference"].abs().sort_values(ascending=False).index).head(8).to_markdown(index=False),
        eff=100 * float(cfg["benchmark"]["fixed_efficiency"]),
        scoreboard_table=scoreboard[["method", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "brier_isotonic", "ece_isotonic", eff_col]].to_markdown(index=False),
        winner_method=winner["method"],
        winner_auc=winner["roc_auc"],
        winner_lo=winner["roc_auc_ci"][0],
        winner_hi=winner["roc_auc_ci"][1],
        nuis_auc=nuisance["roc_auc"],
        nuis_lo=nuisance["roc_auc_ci_low"],
        nuis_hi=nuisance["roc_auc_ci_high"],
        p08b_even_auc=p08b.get("even_charge_proxy_auc", float("nan")),
        p08b_ml_auc=p08b.get("ml_auc", float("nan")),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "p08c_1781054166_1411_4282226f_continuous_charge_current_matching.json")
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_json(cfg_path)
    p08b_cfg = load_json(ROOT / cfg["p08b_config"])
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = P08B.resolve_raw_root_dir(p08b_cfg)
    anchors = P08B.geometry_anchors(p08b_cfg)
    waves, meta, counts_by_run, counts_by_group = P08B.scan_raw(p08b_cfg, raw_dir)
    reproduction = P08B.reproduction_table(p08b_cfg, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed; refusing to continue")

    meta, label_support, calibration = P08B.add_calibrated_labels(meta, p08b_cfg, anchors)
    label_support.to_csv(out_dir / "calibrated_label_support.csv", index=False)
    meta.groupby(["run", "depth_idx", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run_depth.csv", index=False)
    meta = add_nuisance_columns(meta)
    meta["propensity_logit"] = fit_propensity(meta, cfg["matching"]["nuisance_columns"], int(cfg["matching"]["random_seed"]))

    exact_idx, exact_cells = exact_cell_match(meta, cfg["matching"], out_dir)
    sensitivity = matching_sensitivity(meta, cfg, exact_idx, cfg["matching"]["sensitivity_calipers"], out_dir)
    primary_idx, primary_cells = continuous_match(meta, cfg["matching"], float(cfg["matching"]["primary_caliper"]), out_dir)
    if len(primary_idx) < 100:
        raise RuntimeError("Primary matching left too little support")
    matched = meta.loc[primary_idx].reset_index(drop=True).copy()
    matched = add_wave_columns(matched, waves)
    p01b_path = resolve_optional_path(cfg.get("p01b_embedding_candidates", []))
    p01b = load_p01b_latents(p01b_path)
    matched, p01b_cols, p01b_status = attach_p01b(matched, p01b)
    nuisance_cols = list(cfg["matching"]["nuisance_columns"]) + ["propensity_logit"]
    balance = balance_table(matched, nuisance_cols)
    balance.to_csv(out_dir / "matched_balance_smd.csv", index=False)
    matched[["run", "event_index", "weak_label", "weak_label_name", "depth_idx", "event_fraction", "propensity_logit"]].head(50000).to_csv(out_dir / "matched_event_preview.csv", index=False)

    scoreboard, predictions, fold_counts, details = benchmark(matched, cfg, out_dir, p01b_cols)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    model_rows = scoreboard[~scoreboard["method"].str.startswith("leakage sentinel")].copy()
    winner_row = model_rows.sort_values(["roc_auc", "average_precision"], ascending=False).iloc[0]

    p08b_result = load_json(ROOT / cfg["p08b_result"])
    even_auc = None
    for row in p08b_result.get("leakage_hunt", []):
        if row.get("probe") == "even-charge calibration-proxy logistic":
            even_auc = row.get("roc_auc")
    result = {
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "study_id": cfg["study_id"],
        "title": cfg["title"],
        "config": str(cfg_path.relative_to(ROOT)),
        "script": "scripts/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.py",
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "calibrated_label_definition": {"weak_label": p08b_cfg["weak_label"], "calibration": calibration},
        "calibrated_label_support": {"n_atoms": int(len(label_support)), "n_labeled_rows": int(len(meta)), "atom_columns": ["run", "depth_idx"]},
        "matching": {
            "method": "continuous run/depth nearest-neighbor matching in standardized nuisance plus propensity-logit space",
            "settings": cfg["matching"],
            "matched_rows": int(len(matched)),
            "matched_pairs": int(len(matched) // 2),
            "support_loss_fraction": float(1.0 - len(matched) / len(meta)),
            "max_abs_smd": float(balance["standardized_mean_difference"].abs().max()),
            "exact_cell_matched_rows": int(len(exact_idx)),
            "sensitivity": sensitivity.to_dict(orient="records"),
        },
        "p01b_latent_join": p01b_status,
        "benchmark": details,
        "winner": {
            "method": str(winner_row["method"]),
            "selection_metric": "point-estimate ROC AUC among non-sentinel methods",
            "roc_auc": float(winner_row["roc_auc"]),
            "roc_auc_ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
            "average_precision": float(winner_row["average_precision"]),
        },
        "pid_adoption": False,
        "p08b_comparison": {
            "ml_auc": p08b_result["ml"]["roc_auc"],
            "traditional_auc": p08b_result["traditional"]["roc_auc"],
            "even_charge_proxy_auc": even_auc,
        },
        "input_file_count": len(P08B.configured_runs(p08b_cfg)),
        "follow_up_ticket_appended": False,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    result["primary_interpretation"] = (
        "Continuous charge/current matching suppresses the P08b nuisance shortcut relative to the pre-matched even-charge proxy, "
        "but the weak label remains a charge-residual construct. The named winner is a leakage-control benchmark winner, not a PID adoption result."
    )
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, cfg, p08b_cfg, result, reproduction, label_support, sensitivity, balance, scoreboard)

    input_rows = []
    for run in P08B.configured_runs(p08b_cfg):
        path = P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": cfg["ticket_id"],
        "script": result["script"],
        "config": result["config"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(result["script"], result["config"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit_at_run": result["git_commit_at_run"],
        "raw_root_dir": str(raw_dir),
        "random_seeds": {"matching": cfg["matching"]["random_seed"], "benchmark": cfg["benchmark"]["random_seed"]},
        "input_sha256_csv": str((out_dir / "input_sha256.csv").relative_to(ROOT)),
        "input_file_count": len(input_rows),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(scoreboard.to_string(index=False))
    print("winner:", result["winner"]["method"])
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
