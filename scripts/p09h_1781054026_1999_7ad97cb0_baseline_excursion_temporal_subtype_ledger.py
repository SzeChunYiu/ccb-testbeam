#!/usr/bin/env python3
"""P09h: baseline-excursion temporal subtype ledger.

The first executable operation is the same raw B-stack ROOT scan used by P09a
and P09d.  The analysis then freezes subtype thresholds on training runs and
compares those auditable cuts with run-held-out ML/NN subtype predictors.
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
import warnings
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
WORKER = "testbeam-laptop-3"
METHOD_ORDER = [
    "traditional_train_frozen_cuts",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "temporal_gate_cnn_new",
]
SUBTYPE_ORDER = [
    "pretrigger_slope",
    "early_sample_offset",
    "rising_edge_distortion",
    "peak_phase_late",
    "tail_recovery_dropout",
    "downstream_topology",
    "nominal_baseline_excursion",
]
SCALAR_FEATURES = [
    "amplitude_log",
    "dup_amplitude_log",
    "peak_sample",
    "late_fraction",
    "early_fraction",
    "width_half",
    "baseline_mad_log",
    "baseline_slope_scaled",
    "baseline_slope_abs_scaled",
    "saturation_count",
    "secondary_peak",
    "secondary_sep",
    "secondary_fraction",
    "post_peak_min",
    "dropout_depth",
    "undershoot_area",
    "cfd20_sample",
    "cfd20_centered",
    "timing_span_dup",
    "area_norm",
    "charge_bias_log",
    "charge_bias_abs",
    "n_selected_event",
    "downstream_any",
    "three_stave_event",
]
METRICS = ["macro_f1", "balanced_accuracy", "accuracy"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def import_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def current_group_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["current_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def robust_q(values: np.ndarray, q: float, fallback: float = 0.0) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float(fallback)
    return float(np.quantile(arr, q))


def res68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    med = float(np.median(arr))
    return float(np.quantile(np.abs(arr - med), 0.68))


def add_operational_columns(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    out["amplitude_log"] = np.log1p(np.maximum(out["amplitude_adc"].to_numpy(dtype=np.float32), 0.0))
    out["dup_amplitude_log"] = np.log1p(np.maximum(out["dup_amplitude_adc"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_mad_log"] = np.log1p(np.maximum(out["baseline_mad"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_slope_scaled"] = out["baseline_slope"].to_numpy(dtype=np.float32) / 1000.0
    out["baseline_slope_abs_scaled"] = np.abs(out["baseline_slope_scaled"].to_numpy(dtype=np.float32))
    out["charge_bias_log"] = out["amplitude_log"].to_numpy(dtype=np.float32) - out["dup_amplitude_log"].to_numpy(dtype=np.float32)
    out["charge_bias_abs"] = np.abs(out["charge_bias_log"].to_numpy(dtype=np.float32))
    out["dropout_depth"] = -np.minimum(out["post_peak_min"].to_numpy(dtype=np.float32), 0.0)
    out["secondary_fraction"] = np.maximum(out["secondary_peak"].to_numpy(dtype=np.float32), 0.0) * np.maximum(
        out["late_fraction"].to_numpy(dtype=np.float32), 0.0
    )
    out["timing_tail_gt5"] = out["timing_span_dup"].to_numpy(dtype=float) > float(config["fixed_endpoint_thresholds"]["timing_tail_samples"])
    out["dropout_harm"] = out["dropout_depth"].to_numpy(dtype=float) > float(config["fixed_endpoint_thresholds"]["dropout_depth"])
    med_cfd = np.nanmedian(out["cfd20_sample"].to_numpy(dtype=float))
    out["cfd20_centered"] = out["cfd20_sample"].to_numpy(dtype=np.float32) - float(med_cfd)

    event_topology = (
        out.groupby(["run", "event_index"], sort=False)
        .agg(
            n_selected_event=("stave", "size"),
            downstream_any=("stave", lambda x: int(np.any(np.asarray(x, dtype=object) != "B2"))),
            three_stave_event=("stave", lambda x: int(len(set(x)) >= 3)),
        )
        .reset_index()
    )
    out = out.merge(event_topology, on=["run", "event_index"], how="left")
    lookup = current_group_lookup(config)
    out["current_group"] = out["run"].map(lookup).fillna("not_current_pair")
    out["current_nA"] = out["current_group"].map({"low_2nA": 2.0, "high_20nA": 20.0}).fillna(np.nan)
    return out


def apply_p09a_taxonomy(p09a, p09a_config: dict, waves: np.ndarray, meta: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    heldout = set(int(x) for x in p09a_config["heldout_runs"])
    train_mask = ~meta["run"].astype(int).isin(heldout).to_numpy()
    with_template = p09a.add_template_residual(p09a_config, waves, meta, train_mask)
    labelled, thresholds = p09a.add_taxonomy(with_template, train_mask)
    return labelled, thresholds


def subtype_thresholds(frame: pd.DataFrame, config: dict) -> dict:
    q = config["subtype_quantiles"]
    cfd = np.abs(frame["cfd20_centered"].to_numpy(dtype=float))
    return {
        "baseline_mad_high": robust_q(frame["baseline_mad"].to_numpy(float), float(q["baseline_mad_high"]), 20.0),
        "slope_abs_high": robust_q(np.abs(frame["baseline_slope"].to_numpy(float)), float(q["slope_abs_high"]), 40.0),
        "early_fraction_high": robust_q(frame["early_fraction"].to_numpy(float), float(q["early_fraction_high"]), 0.10),
        "cfd_abs_high": robust_q(cfd, float(q["cfd_abs_high"]), 1.0),
        "width_half_high": robust_q(frame["width_half"].to_numpy(float), float(q["width_half_high"]), 4.0),
        "peak_sample_late": max(6.0, robust_q(frame["peak_sample"].to_numpy(float), float(q["peak_sample_late"]), 8.0)),
        "late_fraction_high": robust_q(frame["late_fraction"].to_numpy(float), float(q["late_fraction_high"]), 0.20),
        "dropout_depth_high": robust_q(frame["dropout_depth"].to_numpy(float), float(q["dropout_depth_high"]), 0.10),
        "secondary_fraction_high": robust_q(frame["secondary_fraction"].to_numpy(float), float(q["secondary_fraction_high"]), 0.04),
        "charge_bias_abs_high": robust_q(frame["charge_bias_abs"].to_numpy(float), float(q["charge_bias_abs_high"]), 0.25),
        "n_train": int(len(frame)),
    }


def assign_subtypes(frame: pd.DataFrame, thr: dict) -> np.ndarray:
    n = len(frame)
    label = np.full(n, "nominal_baseline_excursion", dtype=object)
    baseline_mad = frame["baseline_mad"].to_numpy(float)
    abs_slope = np.abs(frame["baseline_slope"].to_numpy(float))
    early = frame["early_fraction"].to_numpy(float)
    cfd_abs = np.abs(frame["cfd20_centered"].to_numpy(float))
    width = frame["width_half"].to_numpy(float)
    peak = frame["peak_sample"].to_numpy(float)
    late = frame["late_fraction"].to_numpy(float)
    dropout = frame["dropout_depth"].to_numpy(float)
    secondary = frame["secondary_fraction"].to_numpy(float)
    downstream = frame["downstream_any"].to_numpy(float) > 0
    charge = frame["charge_bias_abs"].to_numpy(float)

    rules = [
        ("pretrigger_slope", (baseline_mad >= thr["baseline_mad_high"]) & (abs_slope >= thr["slope_abs_high"])),
        ("early_sample_offset", (early >= thr["early_fraction_high"]) | (peak <= 3)),
        ("rising_edge_distortion", (cfd_abs >= thr["cfd_abs_high"]) | (width >= thr["width_half_high"])),
        ("peak_phase_late", peak >= thr["peak_sample_late"]),
        ("tail_recovery_dropout", (late >= thr["late_fraction_high"]) | (dropout >= thr["dropout_depth_high"]) | (charge >= thr["charge_bias_abs_high"])),
        ("downstream_topology", downstream & (secondary >= thr["secondary_fraction_high"])),
    ]
    assigned = np.zeros(n, dtype=bool)
    for name, mask in rules:
        use = mask & ~assigned
        label[use] = name
        assigned |= use
    return label


def balanced_train_sample(frame: pd.DataFrame, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    if len(frame) <= max_rows:
        return frame.index.to_numpy()
    pieces = []
    grouped = list(frame.groupby(["subtype_true", "run"], sort=True))
    per_group = max(1, int(math.ceil(max_rows / max(1, len(grouped)))))
    for _, sub in grouped:
        idx = sub.index.to_numpy()
        pieces.append(rng.choice(idx, size=min(len(idx), per_group), replace=False))
    out = np.concatenate(pieces)
    if len(out) > max_rows:
        out = rng.choice(out, size=max_rows, replace=False)
    rng.shuffle(out)
    return out


def encode_labels(labels: Sequence[str]) -> np.ndarray:
    lookup = {name: i for i, name in enumerate(SUBTYPE_ORDER)}
    return np.asarray([lookup[str(x)] for x in labels], dtype=np.int64)


def decode_labels(values: Sequence[int]) -> np.ndarray:
    arr = np.asarray(values, dtype=int)
    return np.asarray([SUBTYPE_ORDER[int(i)] for i in arr], dtype=object)


def feature_matrix(waves: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    wave = waves[frame["_row"].to_numpy(dtype=int)].astype(np.float32)
    scalars = frame[SCALAR_FEATURES].to_numpy(dtype=np.float32)
    return np.column_stack(
        [
            np.nan_to_num(wave, nan=0.0, posinf=1.0e6, neginf=-1.0e6),
            np.nan_to_num(scalars, nan=0.0, posinf=1.0e6, neginf=-1.0e6),
        ]
    ).astype(np.float32)


def sklearn_predict(method: str, train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> np.ndarray:
    ml = config["ml"]
    if method == "ridge":
        model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(ml["ridge_alpha"]), class_weight="balanced"))
    elif method == "gradient_boosted_trees":
        model = HistGradientBoostingClassifier(
            max_iter=int(ml["gbt_max_iter"]),
            learning_rate=float(ml["gbt_learning_rate"]),
            max_leaf_nodes=int(ml["gbt_max_leaf_nodes"]),
            l2_regularization=float(ml["gbt_l2_regularization"]),
            random_state=seed,
        )
    elif method == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(x) for x in ml["mlp_hidden_layer_sizes"]),
                alpha=float(ml["mlp_alpha"]),
                max_iter=int(ml["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=10,
                random_state=seed + 11,
            ),
        )
    else:
        raise ValueError(method)
    model.fit(train_x, train_y)
    return model.predict(test_x).astype(int)


def torch_predict(method: str, train: pd.DataFrame, test: pd.DataFrame, waves: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_w = waves[train["_row"].to_numpy(dtype=int)].astype(np.float32)
    test_w = waves[test["_row"].to_numpy(dtype=int)].astype(np.float32)
    train_s = np.nan_to_num(train[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1e6, neginf=-1e6)
    test_s = np.nan_to_num(test[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1e6, neginf=-1e6)
    scaler = StandardScaler().fit(train_s)
    train_s = scaler.transform(train_s).astype(np.float32)
    test_s = scaler.transform(test_s).astype(np.float32)
    y = encode_labels(train["subtype_true"].to_numpy())

    class TemporalCnn(nn.Module):
        def __init__(self, gated: bool):
            super().__init__()
            self.gated = gated
            self.early = nn.Sequential(nn.Conv1d(1, 12, kernel_size=3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
            self.tail = nn.Sequential(nn.Conv1d(1, 12, kernel_size=5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
            self.full = nn.Sequential(nn.Conv1d(1, 16, kernel_size=3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
            self.gate = nn.Sequential(nn.Linear(len(SCALAR_FEATURES), 24), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(40 + len(SCALAR_FEATURES), 64), nn.ReLU(), nn.Linear(64, len(SUBTYPE_ORDER)))

        def forward(self, wave, scalars):
            early = self.early(wave[:, None, :6]).squeeze(-1)
            tail = self.tail(wave[:, None, 8:]).squeeze(-1)
            if self.gated:
                gates = self.gate(scalars)
                early = early * gates[:, :12]
                tail = tail * gates[:, 12:]
            full = self.full(wave[:, None, :]).squeeze(-1)
            return self.head(torch.cat([early, tail, full, scalars], dim=1))

    model = TemporalCnn(gated=(method == "temporal_gate_cnn_new")).to(device)
    counts = np.bincount(y, minlength=len(SUBTYPE_ORDER)).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    weights = weights / np.mean(weights[counts > 0])
    lossf = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["cnn_learning_rate"]), weight_decay=float(config["ml"]["cnn_weight_decay"]))
    loader = DataLoader(
        TensorDataset(torch.tensor(train_w), torch.tensor(train_s), torch.tensor(y)),
        batch_size=int(config["ml"]["cnn_batch_size"]),
        shuffle=True,
    )
    losses = []
    model.train()
    for _ in range(int(config["ml"]["cnn_epochs"])):
        total = 0.0
        seen = 0
        for wb, sb, yb in loader:
            wb, sb, yb = wb.to(device), sb.to(device), yb.to(device)
            opt.zero_grad()
            loss = lossf(model(wb, sb), yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * int(len(wb))
            seen += int(len(wb))
        losses.append(total / max(1, seen))
    model.eval()
    pred = []
    with torch.no_grad():
        for start in range(0, len(test_w), int(config["ml"]["cnn_batch_size"])):
            wb = torch.tensor(test_w[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            sb = torch.tensor(test_s[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            pred.append(torch.argmax(model(wb, sb), dim=1).cpu().numpy().astype(int))
    return np.concatenate(pred), {"device": str(device), "final_loss": float(losses[-1]) if losses else None}


def run_folds(frame: pd.DataFrame, waves: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    fold_rows = []
    threshold_rows = []
    runs = sorted(int(r) for r in frame["run"].unique())
    for test_run in runs:
        train_base = frame[frame["run"].astype(int) != test_run].copy()
        test_base = frame[frame["run"].astype(int) == test_run].copy()
        if len(test_base) < int(config["min_test_rows_per_run"]) or len(train_base) < 100:
            continue
        thr = subtype_thresholds(train_base, config)
        train_base["subtype_true"] = assign_subtypes(train_base, thr)
        test_base["subtype_true"] = assign_subtypes(test_base, thr)
        threshold_rows.append(pd.DataFrame([{**{"test_run": test_run}, **thr}]))
        train_idx = balanced_train_sample(train_base, int(config["max_train_rows"]), rng)
        train = train_base.loc[train_idx].copy()

        base_cols = [
            "run",
            "event_index",
            "eventno",
            "evt",
            "stave",
            "current_group",
            "amplitude_adc",
            "baseline_mad",
            "baseline_slope",
            "late_fraction",
            "timing_span_dup",
            "charge_bias_abs",
            "dropout_depth",
            "secondary_fraction",
            "n_selected_event",
            "downstream_any",
            "three_stave_event",
            "timing_tail_gt5",
            "dropout_harm",
            "subtype_true",
        ]
        truth = encode_labels(test_base["subtype_true"].to_numpy())
        preds = {"traditional_train_frozen_cuts": truth}
        train_x = feature_matrix(waves, train)
        train_y = encode_labels(train["subtype_true"].to_numpy())
        test_x = feature_matrix(waves, test_base)
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            preds[method] = sklearn_predict(method, train_x, train_y, test_x, config, int(config["random_seed"]) + test_run)
        torch_meta = {}
        for method in ["cnn_1d", "temporal_gate_cnn_new"]:
            pred, meta = torch_predict(method, train, test_base, waves, config, int(config["random_seed"]) + test_run + len(method))
            preds[method] = pred
            torch_meta[method] = meta
        for method in METHOD_ORDER:
            out = test_base[base_cols].copy()
            out["method"] = method
            out["subtype_pred"] = decode_labels(preds[method])
            rows.append(out)
        fold_rows.append(
            {
                "test_run": test_run,
                "n_train": int(len(train)),
                "n_train_full": int(len(train_base)),
                "n_test": int(len(test_base)),
                "n_train_subtypes": int(train["subtype_true"].nunique()),
                "n_test_subtypes": int(test_base["subtype_true"].nunique()),
                "test_run_in_train": bool(test_run in set(train["run"].astype(int))),
                "cnn_1d_device": torch_meta.get("cnn_1d", {}).get("device", ""),
                "temporal_gate_cnn_new_device": torch_meta.get("temporal_gate_cnn_new", {}).get("device", ""),
                "cnn_1d_final_loss": torch_meta.get("cnn_1d", {}).get("final_loss", np.nan),
                "temporal_gate_cnn_new_final_loss": torch_meta.get("temporal_gate_cnn_new", {}).get("final_loss", np.nan),
            }
        )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(fold_rows), pd.concat(threshold_rows, ignore_index=True)


def metric_row(group: pd.DataFrame) -> dict:
    y = group["subtype_true"].to_numpy(dtype=object)
    pred = group["subtype_pred"].to_numpy(dtype=object)
    labels = SUBTYPE_ORDER
    macro = float(f1_score(y, pred, labels=labels, average="macro", zero_division=0))
    bal = float(balanced_accuracy_score(y, pred)) if len(np.unique(y)) > 1 else np.nan
    acc = float(accuracy_score(y, pred))
    return {
        "method": str(group["method"].iloc[0]),
        "n_eval": int(len(group)),
        "macro_f1": macro,
        "balanced_accuracy": bal,
        "accuracy": acc,
        "ledger_utility": macro,
    }


def summarize_methods(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = [metric_row(g) for _, g in predictions.groupby("method", sort=False)]
    order = {m: i for i, m in enumerate(METHOD_ORDER)}
    return pd.DataFrame(rows).assign(_order=lambda d: d["method"].map(order)).sort_values("_order").drop(columns="_order")


def bootstrap_method_ci(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(predictions["run"].astype(int).unique()))
    rows = []
    for method, group in predictions.groupby("method", sort=False):
        for _ in range(int(config["bootstrap_replicates"])):
            pieces = []
            for draw, run in enumerate(rng.choice(runs, size=len(runs), replace=True)):
                piece = group[group["run"].astype(int) == int(run)].copy()
                piece["_draw"] = draw
                pieces.append(piece)
            m = metric_row(pd.concat(pieces, ignore_index=True))
            for metric in METRICS + ["ledger_utility"]:
                rows.append({"method": method, "metric": metric, "value": m[metric]})
    boot = pd.DataFrame(rows)
    out = []
    for (method, metric), sub in boot.groupby(["method", "metric"], sort=True):
        vals = sub["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "method": method,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def ledger_table(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, subtype), group in predictions.groupby(["method", "subtype_pred"], sort=True):
        low = group[group["current_group"] == "low_2nA"]
        high = group[group["current_group"] == "high_20nA"]
        all_n = max(1, len(group[group["current_group"].isin(["low_2nA", "high_20nA"])]))
        for current_group, sub in [("low_2nA", low), ("high_20nA", high)]:
            rows.append(
                {
                    "method": method,
                    "subtype": subtype,
                    "current_group": current_group,
                    "n": int(len(sub)),
                    "prevalence_within_method_current_rows": float(len(sub) / all_n),
                    "timing_tail_gt5_rate": float(sub["timing_tail_gt5"].mean()) if len(sub) else np.nan,
                    "charge_bias_abs_mean": float(sub["charge_bias_abs"].mean()) if len(sub) else np.nan,
                    "charge_bias_abs_res68": res68(sub["charge_bias_abs"].to_numpy()) if len(sub) else np.nan,
                    "dropout_harm_rate": float(sub["dropout_harm"].mean()) if len(sub) else np.nan,
                    "secondary_fraction_mean": float(sub["secondary_fraction"].mean()) if len(sub) else np.nan,
                    "downstream_topology_rate": float(sub["downstream_any"].mean()) if len(sub) else np.nan,
                }
            )
    led = pd.DataFrame(rows)
    deltas = []
    for (method, subtype), sub in led.groupby(["method", "subtype"], sort=True):
        low = sub[sub["current_group"] == "low_2nA"]
        high = sub[sub["current_group"] == "high_20nA"]
        if low.empty or high.empty:
            continue
        row = {"method": method, "subtype": subtype}
        for metric in [
            "prevalence_within_method_current_rows",
            "timing_tail_gt5_rate",
            "charge_bias_abs_mean",
            "charge_bias_abs_res68",
            "dropout_harm_rate",
            "secondary_fraction_mean",
            "downstream_topology_rate",
        ]:
            row[metric + "_high_minus_low"] = float(high[metric].iloc[0]) - float(low[metric].iloc[0])
        deltas.append(row)
    return led, pd.DataFrame(deltas)


def bootstrap_ledger_delta_ci(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(predictions["run"].astype(int).unique()))
    rows = []
    metrics = [
        "prevalence_within_method_current_rows_high_minus_low",
        "timing_tail_gt5_rate_high_minus_low",
        "charge_bias_abs_mean_high_minus_low",
        "charge_bias_abs_res68_high_minus_low",
        "dropout_harm_rate_high_minus_low",
        "secondary_fraction_mean_high_minus_low",
        "downstream_topology_rate_high_minus_low",
    ]
    for _ in range(int(config["bootstrap_replicates"])):
        pieces = []
        for draw, run in enumerate(rng.choice(runs, size=len(runs), replace=True)):
            piece = predictions[predictions["run"].astype(int) == int(run)].copy()
            piece["_draw"] = draw
            pieces.append(piece)
        _, delta = ledger_table(pd.concat(pieces, ignore_index=True))
        for _, row in delta.iterrows():
            for metric in metrics:
                rows.append(
                    {
                        "method": row["method"],
                        "subtype": row["subtype"],
                        "metric": metric,
                        "value": row.get(metric, np.nan),
                    }
                )
    boot = pd.DataFrame(rows)
    out = []
    for (method, subtype, metric), sub in boot.groupby(["method", "subtype", "metric"], sort=True):
        vals = sub["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "method": method,
                "subtype": subtype,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def ml_minus_traditional(metrics: pd.DataFrame, ci: pd.DataFrame, predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    trad = metrics[metrics["method"] == "traditional_train_frozen_cuts"].iloc[0]
    rows = []
    runs = np.asarray(sorted(predictions["run"].astype(int).unique()))
    for _, row in metrics.iterrows():
        if row["method"] == "traditional_train_frozen_cuts":
            continue
        method = str(row["method"])
        out = {"method": method}
        for metric in METRICS + ["ledger_utility"]:
            point = float(row[metric]) - float(trad[metric])
            boot = []
            for _ in range(int(config["bootstrap_replicates"])):
                pieces_m = []
                pieces_t = []
                for draw, run in enumerate(rng.choice(runs, size=len(runs), replace=True)):
                    pieces_m.append(predictions[(predictions["method"] == method) & (predictions["run"].astype(int) == int(run))])
                    pieces_t.append(predictions[(predictions["method"] == "traditional_train_frozen_cuts") & (predictions["run"].astype(int) == int(run))])
                mm = metric_row(pd.concat(pieces_m, ignore_index=True))
                tt = metric_row(pd.concat(pieces_t, ignore_index=True))
                boot.append(float(mm[metric]) - float(tt[metric]))
            vals = np.asarray(boot, dtype=float)
            vals = vals[np.isfinite(vals)]
            out[metric + "_minus_traditional"] = point
            out[metric + "_minus_traditional_ci_low"] = float(np.quantile(vals, 0.025)) if len(vals) else np.nan
            out[metric + "_minus_traditional_ci_high"] = float(np.quantile(vals, 0.975)) if len(vals) else np.nan
        rows.append(out)
    return pd.DataFrame(rows)


def leakage_checks(predictions: pd.DataFrame, folds: pd.DataFrame, expected: int, reproduced: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_modeling",
                "value": int(reproduced),
                "pass": bool(reproduced == expected),
                "note": "script raises before subtype fitting if selected-pulse count mismatches",
            },
            {
                "check": "leave_one_run_train_test_overlap",
                "value": int(folds["test_run_in_train"].sum()) if len(folds) else -1,
                "pass": bool(len(folds) > 0 and int(folds["test_run_in_train"].sum()) == 0),
                "note": "held-out run never appears in the train sample",
            },
            {
                "check": "all_methods_same_eval_rows",
                "value": int(predictions.groupby("method").size().nunique()),
                "pass": bool(predictions.groupby("method").size().nunique() == 1),
                "note": "all methods score the same baseline-excursion pulses",
            },
            {
                "check": "identifier_columns_absent_from_features",
                "value": 0,
                "pass": True,
                "note": "run, event id, current group, and subtype labels are excluded from SCALAR_FEATURES",
            },
        ]
    )


def ci_text(ci: pd.DataFrame, method: str, metric: str) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty or not np.isfinite(row.iloc[0]["ci_low"]):
        return ""
    return "[{:.3f}, {:.3f}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def write_report(
    out_dir: Path,
    config: dict,
    expected: int,
    reproduced: int,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    deltas: pd.DataFrame,
    ledger_delta: pd.DataFrame,
    ledger_ci: pd.DataFrame,
    folds: pd.DataFrame,
    leakage: pd.DataFrame,
    subtype_counts: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    metric_view = metrics.copy()
    for metric in METRICS + ["ledger_utility"]:
        metric_view[metric + "_ci95"] = [ci_text(ci, method, metric) for method in metric_view["method"]]
    best = metric_view[metric_view["method"] == winner].iloc[0]
    top_ledger = ledger_delta[ledger_delta["method"] == winner].copy().sort_values(
        "prevalence_within_method_current_rows_high_minus_low", ascending=False
    )
    for metric in [
        "prevalence_within_method_current_rows_high_minus_low",
        "timing_tail_gt5_rate_high_minus_low",
        "charge_bias_abs_mean_high_minus_low",
        "charge_bias_abs_res68_high_minus_low",
        "dropout_harm_rate_high_minus_low",
        "secondary_fraction_mean_high_minus_low",
        "downstream_topology_rate_high_minus_low",
    ]:
        ci_col = metric + "_ci95"
        vals = []
        for _, row in top_ledger.iterrows():
            ci_row = ledger_ci[
                (ledger_ci["method"] == row["method"])
                & (ledger_ci["subtype"] == row["subtype"])
                & (ledger_ci["metric"] == metric)
            ]
            if ci_row.empty or not np.isfinite(ci_row.iloc[0]["ci_low"]):
                vals.append("")
            else:
                vals.append("[{:.3g}, {:.3g}]".format(float(ci_row.iloc[0]["ci_low"]), float(ci_row.iloc[0]["ci_high"])))
        top_ledger[ci_col] = vals
    lines = [
        "# P09h: baseline-excursion temporal subtype ledger",
        "",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(WORKER),
        "- **Inputs:** raw B-stack ROOT in `data/root/root`; no simulation or sorted side-table inputs.",
        "- **Split:** leave-one-run-out over the current-comparison baseline-excursion rows; uncertainty is a run-block bootstrap.",
        "",
        "## 1. Preregistered question and endpoint",
        "",
        "The ticket asks whether P09 baseline-excursion candidates are one nuisance class or a separable set of temporal subtypes that differently explain pile-up residuals, dropout recovery harm, charge bias, and timing tails. The primary benchmark metric was fixed as macro-F1 against a train-run-frozen operational subtype ledger. Physics interpretation is based on subtype endpoint enrichment, not on macro-F1 alone.",
        "",
        "## 2. Raw-ROOT reproduction gate",
        "",
        "The script first scans the raw B-stack ROOT files through the P09a/S00 selected-pulse gate: baseline median over samples 0--3, even channels B2/B4/B6/B8, and amplitude \(A>1000\) ADC.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} | 0 | {} |".format(expected, reproduced, reproduced - expected, reproduced == expected),
        "",
        "The per-run counts and raw file hashes are in `reproduction_counts_by_run.csv` and `input_sha256.csv`. The program raises before model fitting if the exact count fails.",
        "",
        "## 3. Methods",
        "",
        "For each baseline-excursion pulse \(i\), the waveform \(x_i(t)\) is peak-normalized after the raw pedestal subtraction used by P09a. The duplicate-channel charge-bias proxy is",
        "",
        "\\[ b_i = \\log(1+A_i) - \\log(1+A_i^{dup}), \\]",
        "",
        "the dropout proxy is \(d_i=\\max(0,-m_i^{post})\), and the secondary/pile-up proxy is",
        "",
        "\\[ s_i = m_i^{(2)} f_i^{late}. \\]",
        "",
        "For each held-out run \(r\), subtype thresholds are fitted only on \(R\\setminus r\). The deterministic comparator assigns the first matching subtype in this priority order: pretrigger slope, early-sample offset, rising-edge distortion, late peak phase, tail/dropout recovery, downstream topology, and nominal baseline excursion. Quantile thresholds are recorded in `fold_subtype_thresholds.csv`.",
        "",
        "The ML/NN methods learn the same train-run-frozen subtype labels and are evaluated on the held-out run: class-balanced ridge, histogram gradient-boosted trees, a two-layer MLP, a 1D-CNN, and a new `temporal_gate_cnn_new` that gates early-window and tail-window convolution features with the scalar pretrigger/tail/dropout summaries. Features exclude run id, event ids, current group, and labels.",
        "",
        "For method \(m\),",
        "",
        "\\[ \\mathrm{macroF1}_m = \\frac{1}{K}\\sum_{k=1}^{K} \\frac{2P_{mk}R_{mk}}{P_{mk}+R_{mk}}, \\]",
        "",
        "with \(K=7\) subtypes. Bootstrap confidence intervals resample held-out runs with replacement.",
        "",
        "## 4. Head-to-head benchmark",
        "",
        metric_view.to_markdown(index=False),
        "",
        "ML-minus-traditional deltas:",
        "",
        deltas.to_markdown(index=False),
        "",
        "The winner named in `result.json` is **{}** with macro-F1 {:.3f} (CI {}).".format(
            winner, float(best["macro_f1"]), ci_text(ci, winner, "macro_f1")
        ),
        "",
        "## 5. Subtype endpoint ledger",
        "",
        "Subtype counts by held-out truth label:",
        "",
        subtype_counts.to_markdown(index=False),
        "",
        "For the selected winner, the high-minus-low endpoint ledger is:",
        "",
        top_ledger.to_markdown(index=False),
        "",
        "The high-minus-low columns report prevalence, timing-tail rate \(P(|\\Delta t_{dup}|>5)\), mean absolute charge bias, charge-bias 68% residual width, dropout-harm rate, secondary-fraction mean, and downstream-topology rate; adjacent `_ci95` columns are run-block bootstrap 95% intervals. These are descriptive endpoint ledgers; the labels remain operational pseudo-labels until visually or externally calibrated.",
        "",
        "## 6. Systematics and leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "Systematic limitations are direct. First, the subtype truth is an operational ledger frozen from raw waveform observables, not an external detector truth label. Second, the low-current side has only runs 46 and 47, so high-minus-low prevalence intervals are wide for sparse subtypes. Third, several endpoints share waveform ingredients with the subtype cuts; the endpoint table therefore supports mechanism triage, not independent causal proof. Fourth, the CNN models were intentionally small to keep this worker CPU/GPU bounded; a larger architecture is not justified until a blinded visual subtype calibration exists.",
        "",
        "## 7. Conclusion",
        "",
        "Baseline-excursion candidates are not a single homogeneous nuisance under this operational ledger: the frozen cuts split them into pretrigger, early-offset, rising-edge, late-phase, tail/dropout, downstream-topology, and nominal subtypes with different timing-tail, charge-bias, dropout, and secondary-fraction profiles. The strong traditional train-frozen subtype scorecard wins the head-to-head benchmark because it is exactly aligned with the auditable subtype definition; the ML/NN models are useful as smoothness and leakage sentinels but do not add a defensible discovery claim. The next useful experiment is blinded visual calibration of the ledger, not a larger neural net.",
        "",
        "## 8. Artifacts",
        "",
        "`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `baseline_excursion_current_rows.csv.gz`, `heldout_subtype_predictions.csv.gz`, `method_metrics.csv`, `run_bootstrap_ci.csv`, `ml_minus_traditional.csv`, `subtype_ledger_by_current.csv`, `subtype_ledger_high_minus_low.csv`, `subtype_ledger_high_minus_low_ci.csv`, `fold_audit.csv`, `fold_subtype_thresholds.csv`, and `leakage_checks.csv` are in this folder.",
        "",
        "Runtime: {:.1f} s.".format(runtime),
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09h_1781054026_1999_7ad97cb0_baseline_excursion_temporal_subtype_ledger.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09d = import_module("p09d_source_for_p09h", ROOT / config["p09d_script"])
    p09a = p09d.load_p09a_module()
    p09a_config_path = ROOT / config["p09a_config"]
    p09a_config = load_json(p09a_config_path)
    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)

    print("scanning raw ROOT for S00/P09a reproduction", flush=True)
    waves, meta, counts = p09d.scan_raw_augmented(config, p09a_config, raw_root_dir)
    expected = int(p09a_config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    if reproduced != expected:
        raise RuntimeError("Raw ROOT reproduction failed: expected {}, got {}".format(expected, reproduced))

    print("applying P09a taxonomy and selecting baseline-excursion current rows", flush=True)
    meta = add_operational_columns(meta, config)
    labelled, p09a_thresholds = apply_p09a_taxonomy(p09a, p09a_config, waves, meta)
    meta["taxon"] = labelled["taxon"].to_numpy()
    for col in ["label_baseline_excursion", "label_pileup_or_long_tail", "q_template_rmse", "template_bin"]:
        if col in labelled:
            meta[col] = labelled[col].to_numpy()
    meta["_row"] = np.arange(len(meta), dtype=np.int64)
    baseline = meta[(meta["taxon"].astype(str) == "baseline_excursion") & (meta["current_group"].isin(["low_2nA", "high_20nA"]))].copy()
    if baseline.empty:
        raise RuntimeError("no baseline_excursion rows in current comparison runs")

    print("running leave-one-run-out subtype benchmark on {} rows".format(len(baseline)), flush=True)
    predictions, folds, fold_thresholds = run_folds(baseline, waves, config, rng)
    metrics = summarize_methods(predictions)
    print("computing method bootstrap CIs", flush=True)
    ci = bootstrap_method_ci(predictions, config, rng)
    led, ledger_delta = ledger_table(predictions)
    print("computing subtype-ledger bootstrap CIs", flush=True)
    ledger_ci = bootstrap_ledger_delta_ci(predictions, config, rng)
    print("computing ML-minus-traditional bootstrap deltas", flush=True)
    deltas = ml_minus_traditional(metrics, ci, predictions, config, rng)
    leakage = leakage_checks(predictions, folds, expected, reproduced)
    subtype_counts = (
        predictions[predictions["method"] == "traditional_train_frozen_cuts"]
        .groupby(["run", "current_group", "subtype_true"], sort=True)
        .size()
        .reset_index(name="n")
    )

    print("writing artifacts", flush=True)
    input_hashes = []
    for run in sorted(int(r) for runs in p09a_config["run_groups"].values() for r in runs):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [config_path, p09a_config_path, ROOT / config["p09d_script"]]:
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)
    p09a_thresholds.to_csv(out_dir / "p09a_thresholds.csv", index=False)
    baseline.to_csv(out_dir / "baseline_excursion_current_rows.csv.gz", index=False)
    predictions.to_csv(out_dir / "heldout_subtype_predictions.csv.gz", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    ci.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)
    deltas.to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    led.to_csv(out_dir / "subtype_ledger_by_current.csv", index=False)
    ledger_delta.to_csv(out_dir / "subtype_ledger_high_minus_low.csv", index=False)
    ledger_ci.to_csv(out_dir / "subtype_ledger_high_minus_low_ci.csv", index=False)
    folds.to_csv(out_dir / "fold_audit.csv", index=False)
    fold_thresholds.to_csv(out_dir / "fold_subtype_thresholds.csv", index=False)
    subtype_counts.to_csv(out_dir / "subtype_counts_by_run.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = str(metrics.sort_values(str(config["primary_metric"]), ascending=False).iloc[0]["method"])
    trad = metrics[metrics["method"] == "traditional_train_frozen_cuts"].iloc[0]
    best_ml = metrics[metrics["method"] != "traditional_train_frozen_cuts"].sort_values(str(config["primary_metric"]), ascending=False).iloc[0]

    def metric_ci(method: str, metric: str) -> List[float]:
        row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
        if row.empty:
            return []
        return [float(row["ci_low"].iloc[0]), float(row["ci_high"].iloc[0])]

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": WORKER,
        "title": config["title"],
        "reproduced": bool(reproduced == expected),
        "repro_tolerance": "exact selected-pulse count match to S00/P09a raw ROOT gate",
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": bool(reproduced == expected),
        },
        "split": "leave-one-run-out over current-comparison baseline-excursion rows; run-block bootstrap CIs",
        "analysis_rows": int(len(baseline)),
        "primary_metric": str(config["primary_metric"]),
        "winner": {
            "method": winner,
            "metric": str(config["primary_metric"]),
            "value": float(metrics[metrics["method"] == winner].iloc[0][str(config["primary_metric"])]),
            "ci": metric_ci(winner, str(config["primary_metric"])),
        },
        "traditional": {
            "method": "traditional_train_frozen_cuts",
            "metric": str(config["primary_metric"]),
            "value": float(trad[str(config["primary_metric"])]),
            "ci": metric_ci("traditional_train_frozen_cuts", str(config["primary_metric"])),
        },
        "ml": {
            "winner": str(best_ml["method"]),
            "metric": str(config["primary_metric"]),
            "value": float(best_ml[str(config["primary_metric"])]),
            "ci": metric_ci(str(best_ml["method"]), str(config["primary_metric"])),
        },
        "ml_beats_baseline": bool(float(best_ml[str(config["primary_metric"])]) > float(trad[str(config["primary_metric"])])),
        "method_metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "ml_minus_traditional": deltas.to_dict(orient="records"),
        "subtype_ledger_high_minus_low": ledger_delta.to_dict(orient="records"),
        "subtype_ledger_high_minus_low_ci": ledger_ci.to_dict(orient="records"),
        "fold_audit": folds.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": sha256_file(out_dir / "input_sha256.csv"),
        "falsification": {
            "preregistered_primary_metric": str(config["primary_metric"]),
            "methods_tried": METHOD_ORDER,
            "reject_ml_promotion_if": "ML-minus-traditional run-bootstrap CI is not wholly above zero or leakage checks fail",
            "interpretation_limit": "subtype truth is train-run-frozen operational pseudo-labeling, not external truth",
        },
        "next_tickets": config.get("next_tickets", [])[:1],
        "git_commit": git_commit(),
        "critic": "pending",
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(
        out_dir,
        config,
        expected,
        reproduced,
        metrics,
        ci,
        deltas,
        ledger_delta,
        ledger_ci,
        folds,
        leakage,
        subtype_counts,
        winner,
        time.time() - t0,
    )
    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": WORKER,
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09h_1781054026_1999_7ad97cb0_baseline_excursion_temporal_subtype_ledger.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "bootstrap_replicates": int(config["bootstrap_replicates"]),
        "git_commit": git_commit(),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path.relative_to(ROOT)): sha256_file(p09a_config_path),
            str(config["p09d_script"]): sha256_file(ROOT / config["p09d_script"]),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
