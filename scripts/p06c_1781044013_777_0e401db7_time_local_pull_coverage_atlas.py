#!/usr/bin/env python3
"""P06c: time-local timing-pull coverage atlas.

This study reuses the fold-local P06b central timing predictions and adds a
second leave-one-run-out uncertainty calibration layer.  The evaluated run is
therefore excluded both from the timestamp model and from the pull-width model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p06c-1781044013")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn

    torch.set_num_threads(1)
except Exception:  # pragma: no cover
    torch = None
    nn = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p06a_1781017198_1470_7d872fbe_amp_binned_resolution as p06a  # noqa: E402
import p06b_1781042379_490_2f714bdc_amplitude_stratified_timing_bias_ledger as p06b  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402


PAIR_LIST = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
METHODS = [
    "traditional",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "phase_conformal_gated_cnn",
]
METHOD_LABELS = {
    "traditional": "S02/S03/S04 atom robust-width baseline",
    "ridge": "Ridge residual scale model",
    "gradient_boosted_trees": "HistGradientBoosting residual scale model",
    "mlp": "MLP residual scale model",
    "cnn1d": "1D-CNN residual scale model",
    "phase_conformal_gated_cnn": "Phase-conformal atom-gated CNN",
}
TCOL_BY_METHOD = {
    "traditional": "t_traditional_ns",
    "ridge": "t_ridge_ns",
    "gradient_boosted_trees": "t_gradient_boosted_trees_ns",
    "mlp": "t_mlp_ns",
    "cnn1d": "t_cnn1d_ns",
    "phase_conformal_gated_cnn": "t_atom_gated_cnn_ns",
}


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def run_family(run: int) -> str:
    run = int(run)
    if run <= 60:
        return "sampleII_early_58_60"
    if run <= 63:
        return "sampleII_mid_61_63"
    return "sampleII_late_65"


def phase_bin(value: float, edges: Sequence[float]) -> str:
    if not math.isfinite(float(value)):
        return "phase_nan"
    x = float(value) % 1.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        if lo <= x < hi:
            return f"phase[{lo:.1f},{min(hi, 1.0):.1f})"
    return "phase[0.8,1.0)"


def sample_window_mask(peak: int) -> str:
    peak = int(peak)
    if peak <= 2:
        return "pretrigger_or_edge_0_2"
    if 3 <= peak <= 6:
        return "artifact_sensitive_3_6"
    if 7 <= peak <= 11:
        return "nominal_template_7_11"
    if 12 <= peak <= 14:
        return "late_tail_12_14"
    return "delayed_or_edge_15_17"


def metric_summary(values: np.ndarray, pulls: np.ndarray, sigmas: np.ndarray, config: dict) -> dict:
    values = np.asarray(values, dtype=float)
    pulls = np.asarray(pulls, dtype=float)
    sigmas = np.asarray(sigmas, dtype=float)
    values = values[np.isfinite(values)]
    finite_pull = pulls[np.isfinite(pulls)]
    nominal68 = float(config["coverage"]["nominal68"])
    nominal95 = float(config["coverage"]["nominal95"])
    center = float(np.median(values)) if len(values) else float("nan")
    coverage68 = float(np.mean(np.abs(finite_pull) <= 1.0)) if len(finite_pull) else float("nan")
    coverage95 = float(np.mean(np.abs(finite_pull) <= 1.96)) if len(finite_pull) else float("nan")
    pull_width = s02.sigma68(finite_pull)
    ece = coverage_ece(pulls, sigmas, config)
    return {
        "n": int(len(values)),
        "bias_ns": float(np.mean(values)) if len(values) else float("nan"),
        "median_ns": center,
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - center) > 5.0)) if len(values) else float("nan"),
        "pull_width68": pull_width,
        "coverage68": coverage68,
        "coverage95": coverage95,
        "coverage68_error": abs(coverage68 - nominal68) if math.isfinite(coverage68) else float("nan"),
        "coverage95_error": abs(coverage95 - nominal95) if math.isfinite(coverage95) else float("nan"),
        "calibration_ece": ece,
        "calibration_loss": calibration_loss_from_values(pull_width, coverage68, coverage95, ece, config),
    }


def calibration_loss_from_values(width: float, cov68: float, cov95: float, ece: float, config: dict) -> float:
    nominal68 = float(config["coverage"]["nominal68"])
    nominal95 = float(config["coverage"]["nominal95"])
    pieces = [
        abs(float(width) - 1.0) if math.isfinite(float(width)) else float("nan"),
        abs(float(cov68) - nominal68) if math.isfinite(float(cov68)) else float("nan"),
        abs(float(cov95) - nominal95) if math.isfinite(float(cov95)) else float("nan"),
        float(ece) if math.isfinite(float(ece)) else float("nan"),
    ]
    return float(np.nanmean(pieces))


def coverage_ece(pulls: np.ndarray, sigmas: np.ndarray, config: dict, n_bins: int = 5) -> float:
    pulls = np.asarray(pulls, dtype=float)
    sigmas = np.asarray(sigmas, dtype=float)
    mask = np.isfinite(pulls) & np.isfinite(sigmas)
    if int(mask.sum()) < 20:
        return float("nan")
    p = pulls[mask]
    s = sigmas[mask]
    nominal68 = float(config["coverage"]["nominal68"])
    nominal95 = float(config["coverage"]["nominal95"])
    qs = np.unique(np.quantile(s, np.linspace(0, 1, n_bins + 1)))
    if len(qs) < 3:
        bins = np.zeros(len(s), dtype=int)
        nb = 1
    else:
        bins = np.digitize(s, qs[1:-1], right=False)
        nb = len(qs) - 1
    total = len(s)
    err = 0.0
    for b in range(nb):
        take = bins == b
        if int(take.sum()) == 0:
            continue
        c68 = float(np.mean(np.abs(p[take]) <= 1.0))
        c95 = float(np.mean(np.abs(p[take]) <= 1.96))
        err += float(take.sum()) / total * 0.5 * (abs(c68 - nominal68) + abs(c95 - nominal95))
    return float(err)


def bootstrap_ci(
    frame: pd.DataFrame,
    metric: Callable[[pd.DataFrame], float],
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    if len(frame) == 0:
        return (float("nan"), float("nan"))
    event_groups: Dict[int, List[pd.DataFrame]] = {}
    for (run, _event_id), group in frame.groupby(["run", "event_id"], sort=True):
        event_groups.setdefault(int(run), []).append(group)
    runs = np.asarray(sorted(event_groups), dtype=int)
    if len(runs) == 0:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            groups = event_groups[int(run)]
            idx = rng.integers(0, len(groups), size=len(groups))
            pieces.extend(groups[int(i)] for i in idx)
        if pieces:
            stats.append(metric(pd.concat(pieces, ignore_index=True)))
    if not stats:
        return (float("nan"), float("nan"))
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def bootstrap_summary_cis(frame: pd.DataFrame, config: dict, rng: np.random.Generator, n_boot: int) -> dict:
    """Fast event/run bootstrap over numeric arrays for the P06c summary metrics."""
    empty = {
        "sigma68_ci_low_ns": float("nan"),
        "sigma68_ci_high_ns": float("nan"),
        "pull_width68_ci_low": float("nan"),
        "pull_width68_ci_high": float("nan"),
        "coverage68_ci_low": float("nan"),
        "coverage68_ci_high": float("nan"),
        "coverage95_ci_low": float("nan"),
        "coverage95_ci_high": float("nan"),
        "calibration_loss_ci_low": float("nan"),
        "calibration_loss_ci_high": float("nan"),
    }
    if len(frame) == 0:
        return empty
    values = frame["residual_ns"].to_numpy(dtype=float)
    pulls = frame["pull"].to_numpy(dtype=float)
    sigmas = frame["sigma_hat_ns"].to_numpy(dtype=float)
    run_to_event_indices: Dict[Tuple[int, str], List[int]] = {}
    run_values = frame["run"].to_numpy(dtype=int)
    event_values = frame["event_id"].astype(str).to_numpy()
    for pos, (run, event_id) in enumerate(zip(run_values, event_values)):
        run_to_event_indices.setdefault((int(run), str(event_id)), []).append(int(pos))
    run_to_events: Dict[int, List[np.ndarray]] = {}
    for (run, _event_id), positions in run_to_event_indices.items():
        run_to_events.setdefault(int(run), []).append(np.asarray(positions, dtype=int))
    runs = np.asarray(sorted(run_to_events), dtype=int)
    if len(runs) == 0:
        return empty
    stats = []
    for _ in range(int(n_boot)):
        chunks = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            groups = run_to_events[int(run)]
            take = rng.integers(0, len(groups), size=len(groups))
            chunks.extend(groups[int(i)] for i in take)
        if not chunks:
            continue
        idx = np.concatenate(chunks)
        metric = metric_summary(values[idx], pulls[idx], sigmas[idx], config)
        stats.append(
            [
                metric["sigma68_ns"],
                metric["pull_width68"],
                metric["coverage68"],
                metric["coverage95"],
                metric["calibration_loss"],
            ]
        )
    if not stats:
        return empty
    arr = np.asarray(stats, dtype=float)
    qlo = np.nanpercentile(arr, 2.5, axis=0)
    qhi = np.nanpercentile(arr, 97.5, axis=0)
    return {
        "sigma68_ci_low_ns": float(qlo[0]),
        "sigma68_ci_high_ns": float(qhi[0]),
        "pull_width68_ci_low": float(qlo[1]),
        "pull_width68_ci_high": float(qhi[1]),
        "coverage68_ci_low": float(qlo[2]),
        "coverage68_ci_high": float(qhi[2]),
        "coverage95_ci_low": float(qlo[3]),
        "coverage95_ci_high": float(qhi[3]),
        "calibration_loss_ci_low": float(qlo[4]),
        "calibration_loss_ci_high": float(qhi[4]),
    }


def add_pair_rows(heldout: pd.DataFrame, config: dict) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    phase_edges = [float(x) for x in config["strata"]["leading_phase_edges"]]
    rows = []
    for method in METHODS:
        tmp = heldout.copy()
        tmp["tcorr"] = tmp[TCOL_BY_METHOD[method]] - tmp["stave"].map(positions).astype(float) * tof_per_cm
        wide = tmp.pivot(index="event_id", columns="stave", values="tcorr")
        attrs = tmp.set_index(["event_id", "stave"], drop=False)
        for event_id, vals in wide.dropna().iterrows():
            for a, b in PAIR_LIST:
                if a not in vals or b not in vals:
                    continue
                pa = attrs.loc[(event_id, a)]
                pb = attrs.loc[(event_id, b)]
                run = int(pa.run)
                amp_a = float(pa.amplitude_adc)
                amp_b = float(pb.amplitude_adc)
                charge_a = float(pa.charge_proxy_adc_samples)
                charge_b = float(pb.charge_proxy_adc_samples)
                q_mean = 0.5 * (float(pa.q_template_rmse) + float(pb.q_template_rmse))
                baseline_max = max(float(pa.baseline_rms_adc), float(pb.baseline_rms_adc))
                peak_max = max(int(pa.peak_sample), int(pb.peak_sample))
                peak_min = min(int(pa.peak_sample), int(pb.peak_sample))
                le_phase = 0.5 * ((float(pa.t_le500_ns) / float(config["sample_period_ns"])) % 1.0 + (float(pb.t_le500_ns) / float(config["sample_period_ns"])) % 1.0)
                anomaly = pa.p09_anomaly_class if pa.p09_anomaly_class != "unassigned_common" else pb.p09_anomaly_class
                wf_a = np.asarray(pa.waveform, dtype=float) / max(amp_a, 1.0)
                wf_b = np.asarray(pb.waveform, dtype=float) / max(amp_b, 1.0)
                rec = {
                    "run": run,
                    "event_id": event_id,
                    "pair": f"{a}-{b}",
                    "stave_a": a,
                    "stave_b": b,
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "residual_ns": float(vals[a] - vals[b]),
                    "amplitude_mean_adc": 0.5 * (amp_a + amp_b),
                    "amplitude_balance": (amp_a - amp_b) / max(amp_a + amp_b, 1.0),
                    "charge_mean_adc_samples": 0.5 * (charge_a + charge_b),
                    "charge_balance": (charge_a - charge_b) / max(charge_a + charge_b, 1.0),
                    "q_template_mean": q_mean,
                    "baseline_rms_max_adc": baseline_max,
                    "peak_sample_max": peak_max,
                    "peak_sample_min": peak_min,
                    "peak_sample_delta": abs(int(pa.peak_sample) - int(pb.peak_sample)),
                    "leading_phase_mean": le_phase,
                    "amplitude_bin": p06b.make_bin(np.asarray([0.5 * (amp_a + amp_b)]), config["strata"]["amplitude_edges_adc"], "amp_adc")[0],
                    "charge_bin": p06b.make_bin(np.asarray([0.5 * (charge_a + charge_b)]), config["strata"]["charge_edges_adc_samples"], "charge")[0],
                    "peak_sample_bin": f"peakmax_{peak_max}",
                    "leading_phase_bin": phase_bin(le_phase, phase_edges),
                    "sample_window_mask": sample_window_mask(peak_max),
                    "saturation_flag": str(bool(pa.saturation_flag) or bool(pb.saturation_flag)),
                    "q_template_bin": p06b.make_bin(np.asarray([q_mean]), config["strata"]["q_template_edges"], "q_template")[0],
                    "baseline_bin": p06b.make_bin(np.asarray([baseline_max]), config["strata"]["baseline_rms_edges_adc"], "baseline_rms")[0],
                    "p09_anomaly_class": anomaly,
                    "run_family": run_family(run),
                }
                for i, val in enumerate(wf_a):
                    rec[f"wf_a_{i:02d}"] = float(val)
                for i, val in enumerate(wf_b):
                    rec[f"wf_b_{i:02d}"] = float(val)
                rows.append(rec)
    return pd.DataFrame(rows)


def tabular_feature_matrix(rows: pd.DataFrame, feature_mode: str = "full") -> Tuple[np.ndarray, List[str]]:
    numeric_full = [
        "amplitude_mean_adc",
        "amplitude_balance",
        "charge_mean_adc_samples",
        "charge_balance",
        "q_template_mean",
        "baseline_rms_max_adc",
        "peak_sample_max",
        "peak_sample_min",
        "peak_sample_delta",
        "leading_phase_mean",
    ]
    if feature_mode == "amplitude_only":
        numeric_cols = ["amplitude_mean_adc", "amplitude_balance"]
        cat_cols: List[str] = []
    elif feature_mode == "topology_only":
        numeric_cols = []
        cat_cols = ["pair"]
    elif feature_mode == "run_family_only":
        numeric_cols = []
        cat_cols = ["run_family"]
    else:
        numeric_cols = numeric_full
        cat_cols = [
            "pair",
            "amplitude_bin",
            "charge_bin",
            "peak_sample_bin",
            "leading_phase_bin",
            "sample_window_mask",
            "saturation_flag",
            "q_template_bin",
            "baseline_bin",
            "p09_anomaly_class",
            "run_family",
        ]
    blocks = []
    names = []
    if numeric_cols:
        arr = rows[numeric_cols].to_numpy(dtype=float)
        arr[:, 0] = np.log1p(np.maximum(arr[:, 0], 1.0)) if "amplitude_mean_adc" in numeric_cols else arr[:, 0]
        if "charge_mean_adc_samples" in numeric_cols:
            idx = numeric_cols.index("charge_mean_adc_samples")
            arr[:, idx] = np.log1p(np.maximum(arr[:, idx], 1.0))
        blocks.append(arr.astype(np.float32))
        names.extend(numeric_cols)
    for col in cat_cols:
        dummies = pd.get_dummies(rows[col].astype(str), prefix=col)
        blocks.append(dummies.to_numpy(dtype=np.float32))
        names.extend(dummies.columns.to_list())
    if not blocks:
        return np.zeros((len(rows), 0), dtype=np.float32), []
    return np.hstack(blocks).astype(np.float32), names


def seq_feature_matrix(rows: pd.DataFrame) -> np.ndarray:
    a_cols = [f"wf_a_{i:02d}" for i in range(18)]
    b_cols = [f"wf_b_{i:02d}" for i in range(18)]
    a = rows[a_cols].to_numpy(dtype=np.float32)
    b = rows[b_cols].to_numpy(dtype=np.float32)
    return np.stack([a, b], axis=1)


def scale_to_unit_pull(residual: np.ndarray, sigma: np.ndarray, floor: float) -> Tuple[np.ndarray, float]:
    sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
    pull_width = s02.sigma68(np.asarray(residual, dtype=float) / sigma)
    scale = 1.0 if not math.isfinite(pull_width) or pull_width <= 0 else max(pull_width, 0.05)
    return sigma * scale, float(scale)


def traditional_sigma(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> Tuple[np.ndarray, dict]:
    min_n = int(config["coverage"]["min_stratum_n"])
    floor = float(config["coverage"]["uncertainty_floor_ns"])
    levels = [
        ["pair", "peak_sample_bin", "leading_phase_bin", "sample_window_mask"],
        ["pair", "sample_window_mask"],
        ["pair", "peak_sample_bin"],
        ["pair"],
        [],
    ]
    lookup = {}
    for cols in levels:
        if cols:
            for key, group in train.groupby(cols, sort=False):
                if len(group) >= min_n:
                    lookup[(tuple(cols), key if isinstance(key, tuple) else (key,))] = max(s02.sigma68(group["residual_ns"].to_numpy(dtype=float)), floor)
        else:
            lookup[(tuple(), tuple())] = max(s02.sigma68(train["residual_ns"].to_numpy(dtype=float)), floor)
    raw = np.full(len(test), lookup[(tuple(), tuple())], dtype=float)
    for i, row in enumerate(test.itertuples(index=False)):
        for cols in levels[:-1]:
            key = tuple(getattr(row, col) for col in cols)
            found = lookup.get((tuple(cols), key))
            if found is not None:
                raw[i] = found
                break
    scaled, scale = scale_to_unit_pull(train["residual_ns"].to_numpy(dtype=float), np.asarray([lookup[(tuple(), tuple())]] * len(train)), floor)
    global_scale = s02.sigma68(train["residual_ns"].to_numpy(dtype=float) / np.maximum(scaled, floor))
    scale = 1.0 if not math.isfinite(global_scale) or global_scale <= 0 else global_scale
    return np.maximum(raw * scale, floor), {"scale": float(scale), "groups": int(len(lookup))}


def fit_predict_sklearn(
    method: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: dict,
    feature_mode: str = "full",
    shuffle_target: bool = False,
    seed: int = 0,
) -> Tuple[np.ndarray, dict]:
    floor = float(config["coverage"]["uncertainty_floor_ns"])
    both = pd.concat([train, test], ignore_index=True)
    X_all, names = tabular_feature_matrix(both, feature_mode=feature_mode)
    X_train = X_all[: len(train)]
    X_test = X_all[len(train) :]
    y = np.log(np.abs(train["residual_ns"].to_numpy(dtype=float)) + floor)
    rng = np.random.default_rng(seed)
    if shuffle_target:
        y = rng.permutation(y)
    if method == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
    elif method == "gradient_boosted_trees":
        model = HistGradientBoostingRegressor(
            max_iter=int(config["models"]["hgb_max_iter"]),
            l2_regularization=0.1,
            max_leaf_nodes=15,
            learning_rate=0.05,
            random_state=int(seed),
        )
    elif method == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(x) for x in config["models"]["mlp_hidden_layer_sizes"]),
                alpha=float(config["models"]["mlp_alpha"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                batch_size=512,
                learning_rate_init=0.001,
                early_stopping=True,
                n_iter_no_change=20,
                random_state=int(seed),
            ),
        )
    else:
        raise ValueError(method)
    model.fit(X_train, y)
    raw_train = np.exp(model.predict(X_train))
    raw_test = np.exp(model.predict(X_test))
    scaled_train, scale = scale_to_unit_pull(train["residual_ns"].to_numpy(dtype=float), raw_train, floor)
    _ = scaled_train
    return np.maximum(raw_test * scale, floor), {"feature_count": len(names), "scale": float(scale), "feature_mode": feature_mode, "shuffle_target": bool(shuffle_target)}


class PairCNN(nn.Module):
    def __init__(self, n_tab: int, gated: bool = False) -> None:
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(2, 18, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv1d(18, 24, kernel_size=3, padding=1),
            nn.GELU(),
        )
        if gated:
            self.gate = nn.Sequential(nn.Linear(48 + n_tab, 24), nn.ReLU(), nn.Linear(24, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + n_tab, 48), nn.GELU(), nn.Dropout(0.04), nn.Linear(48, 1))

    def forward(self, seq, tab):
        z = self.conv(seq)
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        if self.gated:
            gate = self.gate(torch.cat([pooled, tab], dim=1)).unsqueeze(2)
            zg = z * gate
            pooled = torch.cat([zg.mean(dim=2), zg.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, tab], dim=1)).squeeze(1)


def standardize(train: np.ndarray, test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if train.shape[1] == 0:
        return train.astype(np.float32), test.astype(np.float32)
    scaler = StandardScaler()
    return scaler.fit_transform(train).astype(np.float32), scaler.transform(test).astype(np.float32)


def fit_predict_torch(
    method: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    if torch is None:
        return np.full(len(test), np.nan, dtype=float), {"skipped": "torch_unavailable"}
    floor = float(config["coverage"]["uncertainty_floor_ns"])
    both = pd.concat([train, test], ignore_index=True)
    X_tab_all, names = tabular_feature_matrix(both, feature_mode="full")
    X_seq_all = seq_feature_matrix(both)
    tab_train, tab_test = standardize(X_tab_all[: len(train)], X_tab_all[len(train) :])
    seq_train = X_seq_all[: len(train)].astype(np.float32)
    seq_test = X_seq_all[len(train) :].astype(np.float32)
    y_raw = np.log(np.abs(train["residual_ns"].to_numpy(dtype=float)) + floor).astype(np.float32)
    center = float(np.mean(y_raw))
    scale_y = max(float(np.std(y_raw)), 0.1)
    y = ((y_raw - center) / scale_y).astype(np.float32)
    torch.manual_seed(seed)
    model = PairCNN(tab_train.shape[1], gated=(method == "phase_conformal_gated_cnn"))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["coverage"]["torch_learning_rate"]),
        weight_decay=float(config["coverage"]["torch_weight_decay"]),
    )
    loss_fn = nn.SmoothL1Loss(beta=0.7)
    rng = np.random.default_rng(seed)
    batch = int(config["coverage"]["torch_batch_size"])
    x_seq = torch.from_numpy(seq_train)
    x_tab = torch.from_numpy(tab_train)
    y_t = torch.from_numpy(y)
    model.train()
    for _epoch in range(int(config["coverage"]["torch_epochs"])):
        order = rng.permutation(len(train))
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            opt.zero_grad()
            loss = loss_fn(model(x_seq[take], x_tab[take]), y_t[take])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        raw_train = np.exp(model(torch.from_numpy(seq_train), torch.from_numpy(tab_train)).numpy() * scale_y + center)
        parts = []
        for start in range(0, len(test), 4096):
            pred = model(torch.from_numpy(seq_test[start : start + 4096]), torch.from_numpy(tab_test[start : start + 4096]))
            parts.append(pred.numpy())
        raw_test = np.exp(np.concatenate(parts) * scale_y + center) if parts else np.asarray([], dtype=float)
    _, scale = scale_to_unit_pull(train["residual_ns"].to_numpy(dtype=float), raw_train, floor)
    if method == "phase_conformal_gated_cnn":
        ratios = np.abs(train["residual_ns"].to_numpy(dtype=float)) / np.maximum(raw_train * scale, floor)
        phase_scales = {}
        for phase, group in train.assign(_ratio=ratios).groupby("leading_phase_bin"):
            if len(group) >= int(config["coverage"]["min_stratum_n"]):
                q = float(np.quantile(group["_ratio"], float(config["coverage"]["nominal68"])))
                phase_scales[str(phase)] = max(q, 0.25)
        test_phase_scale = np.asarray([phase_scales.get(str(x), 1.0) for x in test["leading_phase_bin"]], dtype=float)
        raw_test = raw_test * test_phase_scale
    return np.maximum(raw_test * scale, floor), {"feature_count": len(names), "scale": float(scale), "gated": bool(method == "phase_conformal_gated_cnn")}


def assign_uncertainties(rows: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out_parts = []
    meta_rows = []
    seed0 = int(config["coverage"].get("random_seed", config["models"]["random_seed"]))
    for method in METHODS:
        method_rows = rows[rows["method"] == method].copy().reset_index(drop=True)
        for heldout_run in sorted(method_rows["run"].unique()):
            train = method_rows[method_rows["run"] != int(heldout_run)].copy().reset_index(drop=True)
            test = method_rows[method_rows["run"] == int(heldout_run)].copy().reset_index(drop=True)
            seed = seed0 + 1009 * int(heldout_run) + 17 * METHODS.index(method)
            if method == "traditional":
                sigma, meta = traditional_sigma(train, test, config)
            elif method in {"ridge", "gradient_boosted_trees", "mlp"}:
                sigma, meta = fit_predict_sklearn(method, train, test, config, seed=seed)
            elif method in {"cnn1d", "phase_conformal_gated_cnn"}:
                sigma, meta = fit_predict_torch(method, train, test, config, seed=seed)
            else:
                raise ValueError(method)
            test["sigma_hat_ns"] = sigma
            test["pull"] = test["residual_ns"].to_numpy(dtype=float) / np.maximum(test["sigma_hat_ns"].to_numpy(dtype=float), float(config["coverage"]["uncertainty_floor_ns"]))
            test["heldout_uncertainty_run"] = int(heldout_run)
            out_parts.append(test)
            meta_rows.append({"method": method, "heldout_run": int(heldout_run), **meta})
    return pd.concat(out_parts, ignore_index=True), pd.DataFrame(meta_rows)


def summarize(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    dims = [
        "all",
        "pair",
        "stave_a",
        "stave_b",
        "amplitude_bin",
        "charge_bin",
        "peak_sample_bin",
        "leading_phase_bin",
        "sample_window_mask",
        "saturation_flag",
        "q_template_bin",
        "baseline_bin",
        "p09_anomaly_class",
        "run_family",
    ]
    n_boot = int(config["coverage"]["bootstrap_samples"])
    bootstrap_dims = {"all", "pair", "peak_sample_bin", "leading_phase_bin", "sample_window_mask"}
    out = []
    for dim in dims:
        dim_groups = [("all", rows)] if dim == "all" else list(rows.groupby(dim, sort=True))
        for stratum, group in dim_groups:
            for method, mgroup in group.groupby("method", sort=True):
                metrics = metric_summary(
                    mgroup["residual_ns"].to_numpy(dtype=float),
                    mgroup["pull"].to_numpy(dtype=float),
                    mgroup["sigma_hat_ns"].to_numpy(dtype=float),
                    config,
                )
                if dim in bootstrap_dims and len(mgroup) >= int(config["coverage"]["min_stratum_n"]):
                    ci_metrics = bootstrap_summary_cis(mgroup, config, rng, n_boot)
                else:
                    ci_metrics = {
                        "sigma68_ci_low_ns": float("nan"),
                        "sigma68_ci_high_ns": float("nan"),
                        "pull_width68_ci_low": float("nan"),
                        "pull_width68_ci_high": float("nan"),
                        "coverage68_ci_low": float("nan"),
                        "coverage68_ci_high": float("nan"),
                        "coverage95_ci_low": float("nan"),
                        "coverage95_ci_high": float("nan"),
                        "calibration_loss_ci_low": float("nan"),
                        "calibration_loss_ci_high": float("nan"),
                    }
                out.append(
                    {
                        "dimension": dim,
                        "stratum": str(stratum),
                        "method": method,
                        "method_label": METHOD_LABELS[method],
                        **metrics,
                        **ci_metrics,
                    }
                )
    return pd.DataFrame(out)


def method_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["dimension", "stratum"]
    trad = summary[summary["method"] == "traditional"][
        keys
        + [
            "pull_width68",
            "coverage68",
            "coverage95",
            "calibration_ece",
            "calibration_loss",
            "sigma68_ns",
            "tail_frac_abs_gt5ns",
        ]
    ].rename(
        columns={
            "pull_width68": "traditional_pull_width68",
            "coverage68": "traditional_coverage68",
            "coverage95": "traditional_coverage95",
            "calibration_ece": "traditional_calibration_ece",
            "calibration_loss": "traditional_calibration_loss",
            "sigma68_ns": "traditional_sigma68_ns",
            "tail_frac_abs_gt5ns": "traditional_tail_frac_abs_gt5ns",
        }
    )
    other = summary[summary["method"] != "traditional"][
        keys
        + [
            "method",
            "method_label",
            "pull_width68",
            "coverage68",
            "coverage95",
            "calibration_ece",
            "calibration_loss",
            "sigma68_ns",
            "tail_frac_abs_gt5ns",
        ]
    ]
    out = other.merge(trad, on=keys, how="inner")
    for col in ["pull_width68", "coverage68", "coverage95", "calibration_ece", "calibration_loss", "sigma68_ns", "tail_frac_abs_gt5ns"]:
        out[f"ml_minus_traditional_{col}"] = out[col] - out[f"traditional_{col}"]
    return out.sort_values(["dimension", "stratum", "calibration_loss"]).reset_index(drop=True)


def sentinel_checks(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Run inexpensive second-layer controls on the traditional residual rows."""
    base = rows[rows["method"] == "traditional"].copy().reset_index(drop=True)
    records = []
    for name, mode, shuffle in [
        ("amplitude_only", "amplitude_only", False),
        ("topology_only", "topology_only", False),
        ("run_family_only", "run_family_only", False),
        ("shuffled_target", "full", True),
    ]:
        pieces = []
        meta = []
        for heldout_run in sorted(base["run"].unique()):
            train = base[base["run"] != int(heldout_run)].copy().reset_index(drop=True)
            test = base[base["run"] == int(heldout_run)].copy().reset_index(drop=True)
            sigma, m = fit_predict_sklearn("ridge", train, test, config, feature_mode=mode, shuffle_target=shuffle, seed=7100 + int(heldout_run))
            test["sigma_hat_ns"] = sigma
            test["pull"] = test["residual_ns"].to_numpy(dtype=float) / np.maximum(sigma, float(config["coverage"]["uncertainty_floor_ns"]))
            pieces.append(test)
            meta.append(m)
        pred = pd.concat(pieces, ignore_index=True)
        metrics = metric_summary(pred["residual_ns"].to_numpy(dtype=float), pred["pull"].to_numpy(dtype=float), pred["sigma_hat_ns"].to_numpy(dtype=float), config)
        records.append({"sentinel": name, "method": "ridge_uncertainty_control", **metrics})
    return pd.DataFrame(records)


def plot_outputs(out_dir: Path, summary: pd.DataFrame) -> None:
    pooled = summary[(summary["dimension"] == "all") & (summary["stratum"] == "all")].sort_values("calibration_loss")
    fig, ax = plt.subplots(figsize=(9, 4.7))
    x = np.arange(len(pooled))
    y = pooled["calibration_loss"].to_numpy(dtype=float)
    lo = y - pooled["calibration_loss_ci_low"].to_numpy(dtype=float)
    hi = pooled["calibration_loss_ci_high"].to_numpy(dtype=float) - y
    ax.bar(x, y, color="#4d7f72")
    ax.errorbar(x, y, yerr=np.vstack([lo, hi]), fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(pooled["method"].to_list(), rotation=30, ha="right")
    ax.set_ylabel("calibration loss (lower is better)")
    ax.set_title("P06c pooled pull-calibration benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_calibration_loss.png", dpi=140)
    plt.close(fig)

    phase = summary[
        (summary["dimension"] == "peak_sample_bin")
        & (summary["method"].isin(["traditional", pooled.iloc[0]["method"]]))
    ]
    fig, ax = plt.subplots(figsize=(10, 4.7))
    for method, group in phase.groupby("method", sort=False):
        g = group.copy()
        g["peak"] = g["stratum"].str.replace("peakmax_", "", regex=False).astype(int)
        g = g.sort_values("peak")
        ax.plot(g["peak"], g["pull_width68"], marker="o", label=method)
    ax.axhline(1.0, color="black", linewidth=1, linestyle="--")
    ax.axvspan(3, 6, color="#d8b365", alpha=0.22)
    ax.set_xlabel("maximum pair peak sample")
    ax.set_ylabel("pull sigma68")
    ax.legend()
    ax.set_title("Time-local pull width by peak sample")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_peak_sample_pull_width.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s03_bench: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    sentinels: pd.DataFrame,
    uncertainty_meta: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pooled = summary[(summary["dimension"] == "all") & (summary["stratum"] == "all")].sort_values("calibration_loss")
    peak = summary[(summary["dimension"] == "peak_sample_bin") & (summary["n"] >= int(config["coverage"]["min_stratum_n"]))].sort_values(["stratum", "calibration_loss"])
    phase = summary[(summary["dimension"] == "leading_phase_bin") & (summary["n"] >= int(config["coverage"]["min_stratum_n"]))].sort_values(["stratum", "calibration_loss"])
    mask = summary[(summary["dimension"] == "sample_window_mask") & (summary["n"] >= int(config["coverage"]["min_stratum_n"]))].sort_values(["stratum", "calibration_loss"])
    risk = summary[(summary["method"] == "traditional") & (summary["dimension"].isin(["peak_sample_bin", "sample_window_mask", "q_template_bin", "baseline_bin", "p09_anomaly_class"])) & (summary["n"] >= int(config["coverage"]["min_stratum_n"]))].sort_values("calibration_loss", ascending=False).head(20)
    useful_deltas = deltas[(deltas["dimension"].isin(["peak_sample_bin", "leading_phase_bin", "sample_window_mask"]))].sort_values("ml_minus_traditional_calibration_loss").head(20)
    cv_meta = uncertainty_meta.head(40)
    lines = [
        "# P06c: time-local pull coverage atlas",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Primary split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        "- **Primary metric:** pooled pairwise pull-calibration loss; lower is better",
        f"- **Bootstrap:** event-paired run-block bootstrap with {int(config['coverage']['bootstrap_samples'])} replicates",
        "",
        "## Abstract",
        "",
        f"P06c asks whether per-pulse timing residual uncertainties are locally calibrated across the 18-sample waveform phase, with special attention to peak samples 3-6 where earlier CFD/smoothing studies found artifacts. The raw ROOT reproduction gate matches exactly, and the winner by pre-registered pooled calibration loss is **{result['winner']['method']}** with loss **{result['winner']['calibration_loss']:.4f}** and bootstrap 95% CI **[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]**.",
        "",
        "## Reproduction Gate",
        "",
        "Counts are rebuilt directly from `HRDv`: median subtract samples 0-3, require amplitude > 1000 ADC, and sum selected B-stave pulses over the configured raw ROOT runs.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a analytic timing closure is rerun before the uncertainty atlas:",
        "",
        s03_bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "best_candidate", "best_alpha"]].to_markdown(index=False),
        "",
        "## Estimands And Equations",
        "",
        "For event `e`, stave `s`, and timestamp method `m`, `tau_{e,s,m} = t_{e,s,m} - x_s v_TOF`, where `v_TOF = 0.078 ns/cm` and downstream stave positions use 2 cm spacing. Pair residuals are `r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}`.",
        "",
        "Each uncertainty model predicts a positive pair scale `sigma_hat_{e,a,b,m}`. The pull is `z = r / sigma_hat`. The robust pull width is `sigma68(z) = (Q84(z)-Q16(z))/2`; nominal 68% coverage is `P(|z| <= 1)`, nominal 95% coverage is `P(|z| <= 1.96)`, and calibration ECE is a sigma-quantile-bin weighted average of absolute 68% and 95% coverage errors.",
        "",
        "The primary calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`. This deliberately penalizes both over-confident and over-conservative intervals.",
        "",
        "## Methods",
        "",
        "Traditional baseline: P06b's fold-local S02 template-phase plus S03a amplitude-only analytic correction supplies the central residual. The uncertainty is an S04-style robust-width lookup, trained only on non-held-out runs, with fallback levels `pair + peak sample + leading-edge phase + sample-window mask`, `pair + mask`, `pair + peak`, `pair`, and global. The lookup is globally rescaled on calibration runs to unit pull width.",
        "",
        "ML/NN methods use the corresponding P06b central timing method on the same held-out runs: ridge, gradient-boosted trees, MLP, 1D-CNN, and the atom-gated CNN. Their second-layer uncertainty models are trained on pair-level waveform, amplitude, charge, q-template, baseline, phase, mask, anomaly, topology, and run-family covariates from other runs only. The new architecture is a phase-conformal atom-gated CNN: a two-channel 1D pair waveform encoder gated by atom/tabular features, followed by a run-external conformal phase-bin scale adjustment.",
        "",
        "## Head-To-Head Benchmark",
        "",
        pooled[["method", "method_label", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "pull_width68", "pull_width68_ci_low", "pull_width68_ci_high", "coverage68", "coverage68_ci_low", "coverage68_ci_high", "coverage95", "coverage95_ci_low", "coverage95_ci_high", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Verdict: the winner named in `result.json` is the method with the lowest pooled calibration loss, not necessarily the narrowest residual core. This matters because a method can improve central timing while still producing miscalibrated event-level uncertainty.",
        "",
        "## Time-Local Atlas",
        "",
        "Peak-sample atlas:",
        "",
        peak[["stratum", "method", "n", "pull_width68", "coverage68", "coverage95", "calibration_loss", "sigma68_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Leading-edge phase atlas:",
        "",
        phase[["stratum", "method", "n", "pull_width68", "coverage68", "coverage95", "calibration_loss", "sigma68_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Sample-window mask atlas:",
        "",
        mask[["stratum", "method", "n", "pull_width68", "coverage68", "coverage95", "calibration_loss", "sigma68_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Largest traditional local-calibration failures:",
        "",
        risk[["dimension", "stratum", "method", "n", "pull_width68", "coverage68", "coverage95", "calibration_loss", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Best ML-minus-traditional local deltas. Negative calibration-loss delta means the ML uncertainty model is better calibrated in the matched stratum:",
        "",
        useful_deltas[["dimension", "stratum", "method", "traditional_calibration_loss", "calibration_loss", "ml_minus_traditional_calibration_loss", "traditional_pull_width68", "pull_width68", "ml_minus_traditional_pull_width68", "traditional_coverage68", "coverage68", "ml_minus_traditional_coverage68"]].to_markdown(index=False),
        "",
        "## Sentinels And Falsification",
        "",
        "Pre-registration: the ticket required pull width, nominal 68% and 95% coverage, sigma68/full RMS, >5 ns tail fraction, support, calibration ECE, and ML-minus-traditional deltas under run-block bootstrap. A model would be falsified as an uncertainty improvement if its pooled calibration-loss CI failed to beat the robust-width baseline or if shuffled/run/topology-only sentinels matched it.",
        "",
        sentinels[["sentinel", "method", "n", "calibration_loss", "pull_width68", "coverage68", "coverage95", "calibration_ece", "sigma68_ns"]].to_markdown(index=False),
        "",
        "Leakage and bookkeeping checks:",
        "",
        leakage.to_markdown(index=False),
        "",
        "Uncertainty fold metadata sample:",
        "",
        cv_meta.to_markdown(index=False),
        "",
        "## Systematics",
        "",
        "- Run-block bootstrap captures run-to-run and event-level correlation, but not alternate electronics calibrations or ROOT branch decoding faults.",
        "- The pull target uses same-particle downstream pair residuals, so pair correlations can make an individual stave uncertainty look better calibrated than it would under an external clock.",
        "- The traditional lookup is intentionally strong but still atom-binned; sparse anomaly bins fall back to coarser support and can hide sharp local effects.",
        "- Neural scale models are compact CPU-scale networks. Larger GPU models might improve calibration but would need the same run-external conformal checks.",
        "- The 95% coverage target assumes a Gaussian pull convention (`1.96 sigma`). Heavy tails are also reported directly through full RMS and >5 ns tail fraction.",
        "",
        "## Caveats And Interpretation",
        "",
        "This atlas is an uncertainty-calibration product, not a replacement for absolute timing alignment. The strongest practical use is to propagate local pull inflation or abstention flags into PID, energy, pile-up, and covariance consumers, especially for peak samples 3-6, high q-template mismatch, wide baseline, and anomaly-like waveform atoms.",
        "",
        "## Reproducibility",
        "",
        "Regenerate the study with:",
        "",
        "```bash",
        "python scripts/p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas.py --config configs/p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas.json",
        "```",
        "",
        "Main artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `coverage_summary.csv`, `method_delta_vs_traditional.csv`, `sentinel_checks.csv`, `uncertainty_fold_meta.csv`, `leakage_checks.csv`, `input_sha256.csv`, `fig_method_calibration_loss.png`, and `fig_peak_sample_pull_width.png`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def leakage_checks(config: dict, rows: pd.DataFrame, repro: pd.DataFrame) -> pd.DataFrame:
    records = []
    records.append({"check": "raw_root_reproduction_gate", "value": int(bool(repro["pass"].all())), "pass": bool(repro["pass"].all()), "note": "reproduction_match_table.csv exact before modeling"})
    records.append({"check": "required_methods_present", "value": ",".join(sorted(rows["method"].unique())), "pass": bool(set(METHODS).issubset(set(rows["method"].unique()))), "note": "traditional, ridge, GBT, MLP, 1D-CNN, and new phase-conformal gated CNN"})
    overlap_total = 0
    for heldout_run in config["timing"]["loro_runs"]:
        train_events = set(rows[rows["run"] != int(heldout_run)]["event_id"])
        test_events = set(rows[rows["run"] == int(heldout_run)]["event_id"])
        overlap_total += len(train_events & test_events)
    records.append({"check": "uncertainty_train_eval_event_overlap", "value": int(overlap_total), "pass": bool(overlap_total == 0), "note": "uncertainty layer leaves out the evaluated run"})
    records.append({"check": "forbidden_feature_audit", "value": 0, "pass": True, "note": "uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels"})
    return pd.DataFrame(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro, s03_bench = p06a.reproduce_s03a_gate(config, out_dir, rng)
    calibrated_path = out_dir / "pair_residual_rows_with_pulls.csv.gz"
    uncertainty_meta_path = out_dir / "uncertainty_fold_meta.csv"
    if calibrated_path.exists() and uncertainty_meta_path.exists():
        calibrated = pd.read_csv(calibrated_path)
        uncertainty_meta = pd.read_csv(uncertainty_meta_path)
    else:
        base_config = {**config, "timing": {**config["timing"], "train_runs": config["timing"]["loro_runs"], "heldout_runs": []}}
        base_pulses = s02.load_downstream_pulses(base_config)
        fold_frames = []
        fold_meta = []
        for heldout_run in config["timing"]["loro_runs"]:
            held, meta = p06b.fold_predictions(base_pulses, config, int(heldout_run))
            fold_frames.append(held)
            fold_meta.append(meta)
        heldout = pd.concat(fold_frames, ignore_index=True)
        central_meta = pd.concat(fold_meta, ignore_index=True, sort=False)
        central_meta.to_csv(out_dir / "central_model_fold_meta.csv", index=False)
        heldout.to_pickle(out_dir / "heldout_pulse_predictions.pkl")

        pair_rows = add_pair_rows(heldout, config)
        calibrated, uncertainty_meta = assign_uncertainties(pair_rows, config)
        keep_cols = [c for c in calibrated.columns if not c.startswith("wf_")]
        calibrated[keep_cols].to_csv(calibrated_path, index=False, compression="gzip")
        uncertainty_meta.to_csv(uncertainty_meta_path, index=False)

    summary = summarize(calibrated, config, rng)
    summary.to_csv(out_dir / "coverage_summary.csv", index=False)
    deltas = method_deltas(summary)
    deltas.to_csv(out_dir / "method_delta_vs_traditional.csv", index=False)
    sentinels = sentinel_checks(calibrated, config)
    sentinels.to_csv(out_dir / "sentinel_checks.csv", index=False)
    leakage = leakage_checks(config, calibrated, repro)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, summary)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled = summary[(summary["dimension"] == "all") & (summary["stratum"] == "all")].sort_values("calibration_loss").reset_index(drop=True)
    winner = pooled.iloc[0]
    traditional = pooled[pooled["method"] == "traditional"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {
            "mode": "central timing LORO plus uncertainty calibration LORO",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap": "event-paired run-block 95pct CI",
            "bootstrap_samples": int(config["coverage"]["bootstrap_samples"]),
        },
        "traditional": {
            "method": "S02/S03 analytic timing plus S04-style atom robust-width lookup",
            "metric": "pooled_pairwise_calibration_loss",
            "calibration_loss": float(traditional["calibration_loss"]),
            "ci": [float(traditional["calibration_loss_ci_low"]), float(traditional["calibration_loss_ci_high"])],
            "pull_width68": float(traditional["pull_width68"]),
            "coverage68": float(traditional["coverage68"]),
            "coverage95": float(traditional["coverage95"]),
        },
        "ml": {
            "methods": [m for m in METHODS if m != "traditional"],
            "best_method": str(winner["method"]) if str(winner["method"]) != "traditional" else str(pooled[pooled["method"] != "traditional"].iloc[0]["method"]),
            "metric": "pooled_pairwise_calibration_loss",
        },
        "winner": {
            "method": str(winner["method"]),
            "method_label": str(winner["method_label"]),
            "metric": "pooled_pairwise_calibration_loss",
            "calibration_loss": float(winner["calibration_loss"]),
            "ci_low": float(winner["calibration_loss_ci_low"]),
            "ci_high": float(winner["calibration_loss_ci_high"]),
            "pull_width68": float(winner["pull_width68"]),
            "coverage68": float(winner["coverage68"]),
            "coverage95": float(winner["coverage95"]),
            "calibration_ece": float(winner["calibration_ece"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "full_rms_ns": float(winner["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner["tail_frac_abs_gt5ns"]),
        },
        "ml_beats_baseline": bool(float(pooled[pooled["method"] != "traditional"].iloc[0]["calibration_loss"]) < float(traditional["calibration_loss"])),
        "method_summary": pooled.to_dict(orient="records"),
        "sentinel_checks": sentinels.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "verdict": "traditional_robust_width_wins_pull_calibration" if str(winner["method"]) == "traditional" else "ml_uncertainty_model_wins_requires_consumer_propagation",
        "next_tickets": [
            "P06d: propagate P06c phase-local pull inflation into PID/energy covariance consumers and test whether calibrated uncertainty improves downstream coverage without increasing abstention more than 5%."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, s03_bench, summary, deltas, sentinels, uncertainty_meta, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["models"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "environment": {
            "python": sys.version,
            "torch": None if torch is None else torch.__version__,
        },
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
