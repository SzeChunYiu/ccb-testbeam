#!/usr/bin/env python3
"""P09e: broad-template-mismatch low-positive audit and model benchmark.

The first data operation is a raw ROOT scan through the P09a reader.  The script
raises before any model fit if the selected B-stave pulse count does not
reproduce the frozen S00/P09a count.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


TARGET = "novel_broad_template_mismatch"
METRICS = ["average_precision", "roc_auc", "balanced_accuracy", "recall_at_1pct", "precision_at_1pct"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_z(values: np.ndarray, train_values: np.ndarray) -> np.ndarray:
    train_values = np.asarray(train_values, dtype=float)
    values = np.asarray(values, dtype=float)
    med = float(np.nanmedian(train_values))
    mad = float(np.nanmedian(np.abs(train_values - med)))
    scale = 1.4826 * mad if mad > 1.0e-12 else float(np.nanstd(train_values))
    if not np.isfinite(scale) or scale <= 1.0e-12:
        scale = 1.0
    return (values - med) / scale


def add_broad_subtypes(meta: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    thr = dict(zip(thresholds["threshold"], thresholds["value"]))
    out = meta.copy()
    known = out["label_known_any"].to_numpy(dtype=bool)
    early = out["label_novel_early_pretrigger"].to_numpy(dtype=bool)
    delayed = out["label_novel_delayed_peak"].to_numpy(dtype=bool)
    pileup = out["label_pileup_or_long_tail"].to_numpy(dtype=bool)
    sat = out["label_saturation"].to_numpy(dtype=bool)
    broad_width = (out["width_half"].to_numpy(dtype=float) > float(thr["width_half_q995"])) & ~pileup & ~sat
    q_template_only = (
        (out["q_template_rmse"].to_numpy(dtype=float) > float(thr["q_template_rmse_q995"]))
        & ~known
        & ~early
        & ~delayed
        & ~broad_width
    )
    p09a_strict_q_template_only = (
        (out["q_template_rmse"].to_numpy(dtype=float) > float(thr["q_template_rmse_q999"]))
        & ~known
        & ~early
        & ~delayed
        & ~broad_width
    )
    out["broad_width_source"] = broad_width
    out["q_template_only_source"] = q_template_only
    out["p09a_strict_q_template_only_source"] = p09a_strict_q_template_only
    out["label_gallery_qtemplate_or_broad"] = q_template_only | broad_width
    out["broad_source"] = np.where(
        broad_width & q_template_only,
        "both",
        np.where(broad_width, "broad_width", np.where(q_template_only, "q_template_only", "not_broad_rule")),
    )
    return out


def add_propagation_features(meta: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = meta.copy()
    out["charge_area_proxy"] = out["area_norm"].astype(float)
    out["charge_log_amp"] = np.log1p(out["amplitude_adc"].astype(float))
    train = out.loc[train_mask]
    out["pileup_score"] = np.maximum(
        robust_z(out["secondary_peak"].to_numpy(float), train["secondary_peak"].to_numpy(float)),
        robust_z(out["late_fraction"].to_numpy(float), train["late_fraction"].to_numpy(float)),
    )
    out["baseline_score"] = np.maximum(
        robust_z(out["baseline_mad"].to_numpy(float), train["baseline_mad"].to_numpy(float)),
        np.abs(robust_z(out["baseline_slope"].to_numpy(float), train["baseline_slope"].to_numpy(float))),
    )
    out["timing_score"] = robust_z(out["timing_span_dup"].to_numpy(float), train["timing_span_dup"].to_numpy(float))
    out["charge_score"] = np.abs(
        robust_z(out["charge_area_proxy"].to_numpy(float), train["charge_area_proxy"].to_numpy(float))
    )
    thresholds = pd.DataFrame(
        [
            {"name": "baseline_score_q995_train", "value": float(out.loc[train_mask, "baseline_score"].quantile(0.995))},
            {"name": "pileup_score_q995_train", "value": float(out.loc[train_mask, "pileup_score"].quantile(0.995))},
            {"name": "charge_score_q995_train", "value": float(out.loc[train_mask, "charge_score"].quantile(0.995))},
            {"name": "timing_score_q990_train", "value": float(out.loc[train_mask, "timing_score"].quantile(0.990))},
        ]
    )
    lookup = dict(zip(thresholds["name"], thresholds["value"]))
    out["prop_baseline_excursion"] = out["baseline_score"] > lookup["baseline_score_q995_train"]
    out["prop_pileup_like"] = out["pileup_score"] > lookup["pileup_score_q995_train"]
    out["prop_charge_outlier"] = out["charge_score"] > lookup["charge_score_q995_train"]
    out["prop_timing_tail"] = out["timing_score"] > lookup["timing_score_q990_train"]
    out["prop_veto_like"] = (
        out["prop_baseline_excursion"]
        | out["prop_pileup_like"]
        | out["prop_charge_outlier"]
        | out["prop_timing_tail"]
        | out["label_dropout"]
        | out["label_saturation"]
    )
    out["label_broad_charge_outlier"] = out["label_gallery_qtemplate_or_broad"] & out["prop_charge_outlier"]
    out["label_broad_veto_like"] = out["label_gallery_qtemplate_or_broad"] & out["prop_veto_like"]
    return out, thresholds


def prepare_from_scan(
    p09a,
    p09a_config: dict,
    waves: np.ndarray,
    meta: pd.DataFrame,
    heldout_runs: Sequence[int],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    heldout = set(int(r) for r in heldout_runs)
    heldout_mask = meta["run"].isin(heldout).to_numpy()
    train_mask = ~heldout_mask
    out = p09a.add_template_residual(p09a_config, waves, meta, train_mask)
    out, p09a_thresholds = p09a.add_taxonomy(out, train_mask)
    out = add_broad_subtypes(out, p09a_thresholds)
    out, prop_thresholds = add_propagation_features(out, train_mask)
    return out, p09a_thresholds, prop_thresholds, train_mask, heldout_mask


def audit_indices(meta: pd.DataFrame, mask: np.ndarray, normal_ratio: int, rng: np.random.Generator) -> np.ndarray:
    candidate = mask & meta["label_gallery_qtemplate_or_broad"].to_numpy(dtype=bool)
    normal = mask & (meta["taxon"].to_numpy(dtype=object) == "unassigned_common")
    candidate_idx = np.where(candidate)[0]
    normal_idx = np.where(normal)[0]
    take = min(len(normal_idx), max(1, int(normal_ratio) * max(1, len(candidate_idx))))
    if take:
        normal_take = rng.choice(normal_idx, size=take, replace=False)
        out = np.concatenate([candidate_idx, normal_take])
    else:
        out = candidate_idx
    rng.shuffle(out)
    return out


def balanced_train_indices(
    meta: pd.DataFrame,
    train_audit_idx: np.ndarray,
    target_col: str,
    neg_ratio: int,
    max_rows: int,
    rng: np.random.Generator,
) -> np.ndarray:
    y = meta.loc[train_audit_idx, target_col].to_numpy(dtype=bool)
    pos = train_audit_idx[y]
    neg = train_audit_idx[~y]
    neg_take = min(len(neg), max(len(pos) * int(neg_ratio), 1000 if len(pos) else 0))
    pieces = []
    if len(pos):
        pieces.append(pos)
    if neg_take:
        pieces.append(rng.choice(neg, size=neg_take, replace=False))
    if not pieces:
        raise RuntimeError("No training rows available for benchmark")
    idx = np.concatenate(pieces)
    if len(idx) > max_rows:
        keep_pos = pos
        remaining = max(0, max_rows - len(keep_pos))
        keep_neg = rng.choice(neg, size=min(remaining, len(neg)), replace=False) if remaining else np.asarray([], dtype=int)
        idx = np.concatenate([keep_pos, keep_neg])
    rng.shuffle(idx)
    return idx


def scalar_feature_frame(meta: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    cols = [
        "amplitude_adc",
        "q_template_rmse",
        "width_half",
        "peak_sample",
        "area_norm",
        "late_fraction",
        "early_fraction",
        "baseline_mad",
        "baseline_slope",
        "saturation_count",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "undershoot_area",
        "timing_span_dup",
        "charge_log_amp",
    ]
    return meta.loc[:, cols].astype(float), cols


def standardize(train_idx: np.ndarray, all_x: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler().fit(all_x[train_idx])
    return scaler.transform(all_x).astype(np.float32), scaler


def normalize_score(score: np.ndarray) -> np.ndarray:
    s = np.asarray(score, dtype=float)
    finite = np.isfinite(s)
    out = np.zeros(len(s), dtype=np.float32)
    if finite.sum() == 0:
        return out
    lo, hi = np.nanpercentile(s[finite], [1, 99])
    if not np.isfinite(hi - lo) or hi <= lo:
        out[finite] = s[finite]
        return out
    out[finite] = np.clip((s[finite] - lo) / (hi - lo), 0.0, 1.0)
    return out


def traditional_score(meta: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    train = meta.loc[train_mask]
    qz = robust_z(meta["q_template_rmse"].to_numpy(float), train["q_template_rmse"].to_numpy(float))
    wz = robust_z(meta["width_half"].to_numpy(float), train["width_half"].to_numpy(float))
    cz = np.abs(robust_z(meta["area_norm"].to_numpy(float), train["area_norm"].to_numpy(float)))
    bz = robust_z(meta["baseline_mad"].to_numpy(float), train["baseline_mad"].to_numpy(float))
    pz = robust_z(meta["secondary_peak"].to_numpy(float), train["secondary_peak"].to_numpy(float))
    tz = robust_z(meta["timing_span_dup"].to_numpy(float), train["timing_span_dup"].to_numpy(float))
    return (np.maximum(qz, wz) + 0.30 * cz + 0.20 * np.maximum.reduce([bz, pz, tz])).astype(np.float32)


def fit_ridge(x: np.ndarray, y: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    clf = RidgeClassifier(alpha=1.0, class_weight="balanced", random_state=17)
    clf.fit(x[train_idx], y[train_idx])
    return clf.decision_function(x).astype(np.float32)


def fit_gbt(config: dict, x: np.ndarray, y: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    params = config["gbt"]
    yt = y[train_idx]
    pos = max(1, int(yt.sum()))
    neg = max(1, int((yt == 0).sum()))
    weights = np.where(yt == 1, neg / pos, 1.0).astype(np.float32)
    clf = HistGradientBoostingClassifier(
        max_iter=int(params["max_iter"]),
        learning_rate=float(params["learning_rate"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        l2_regularization=float(params["l2_regularization"]),
        random_state=int(config["random_seed"]) + 41,
    )
    clf.fit(x[train_idx], yt, sample_weight=weights)
    return clf.predict_proba(x)[:, 1].astype(np.float32)


class TorchModels:
    @staticmethod
    def mlp(n_features: int, hidden: int):
        import torch.nn as nn

        return nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Dropout(0.08),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    @staticmethod
    def cnn():
        import torch.nn as nn

        return nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(24, 1),
        )


def fit_torch_single_input(
    x: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    model_kind: str,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, (Path("/proc/cpuinfo").read_text().count("processor\t:") if Path("/proc/cpuinfo").exists() else 4))))
    device = torch.device("cpu")
    tx = torch.tensor(x[train_idx], dtype=torch.float32)
    ty = torch.tensor(y[train_idx], dtype=torch.float32).view(-1, 1)
    if model_kind == "cnn":
        tx = tx.view(tx.shape[0], 1, tx.shape[1])
        model = TorchModels.cnn().to(device)
    else:
        model = TorchModels.mlp(x.shape[1], int(config["torch"]["hidden_dim"])).to(device)
    pos = max(1.0, float(ty.sum().item()))
    neg = max(1.0, float(len(ty) - pos))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch"]["learning_rate"]), weight_decay=1e-4)
    loader = DataLoader(TensorDataset(tx, ty), batch_size=int(config["torch"]["batch_size"]), shuffle=True)
    losses = []
    for _ in range(int(config["torch"]["epochs"])):
        model.train()
        total = 0.0
        seen = 0
        for bx, by in loader:
            bx = bx.to(device)
            by = by.to(device)
            opt.zero_grad()
            logits = model(bx)
            loss = loss_fn(logits, by)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(bx)
            seen += len(bx)
        losses.append(total / max(1, seen))
    scores = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x), int(config["torch"]["batch_size"])):
            bx = torch.tensor(x[start : start + int(config["torch"]["batch_size"])], dtype=torch.float32)
            if model_kind == "cnn":
                bx = bx.view(bx.shape[0], 1, bx.shape[1])
            logits = model(bx.to(device)).cpu().numpy().reshape(-1)
            scores.append(logits.astype(np.float32))
    return np.concatenate(scores), {"final_loss": float(losses[-1]), "losses": [float(v) for v in losses], "device": str(device)}


def fit_hybrid(waves: np.ndarray, scalars: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    class Hybrid(nn.Module):
        def __init__(self, n_scalar: int, hidden: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            self.scalar = nn.Sequential(nn.Linear(n_scalar, hidden), nn.ReLU(), nn.Dropout(0.08))
            self.gate = nn.Sequential(nn.Linear(hidden, 24), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(24 + hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

        def forward(self, wave, scalar):
            w = self.conv(wave)
            s = self.scalar(scalar)
            w = w * self.gate(s)
            return self.head(torch.cat([w, s], dim=1))

    torch.manual_seed(int(config["random_seed"]) + 73)
    torch.set_num_threads(max(1, min(4, (Path("/proc/cpuinfo").read_text().count("processor\t:") if Path("/proc/cpuinfo").exists() else 4))))
    device = torch.device("cpu")
    tw = torch.tensor(waves[train_idx], dtype=torch.float32).view(len(train_idx), 1, waves.shape[1])
    ts = torch.tensor(scalars[train_idx], dtype=torch.float32)
    ty = torch.tensor(y[train_idx], dtype=torch.float32).view(-1, 1)
    model = Hybrid(scalars.shape[1], int(config["torch"]["hidden_dim"])).to(device)
    pos = max(1.0, float(ty.sum().item()))
    neg = max(1.0, float(len(ty) - pos))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch"]["learning_rate"]), weight_decay=1e-4)
    loader = DataLoader(TensorDataset(tw, ts, ty), batch_size=int(config["torch"]["batch_size"]), shuffle=True)
    losses = []
    for _ in range(int(config["torch"]["epochs"])):
        model.train()
        total = 0.0
        seen = 0
        for bw, bs, by in loader:
            bw = bw.to(device)
            bs = bs.to(device)
            by = by.to(device)
            opt.zero_grad()
            loss = loss_fn(model(bw, bs), by)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(bw)
            seen += len(bw)
        losses.append(total / max(1, seen))
    scores = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(waves), int(config["torch"]["batch_size"])):
            bw = torch.tensor(waves[start : start + int(config["torch"]["batch_size"])], dtype=torch.float32).view(-1, 1, waves.shape[1])
            bs = torch.tensor(scalars[start : start + int(config["torch"]["batch_size"])], dtype=torch.float32)
            scores.append(model(bw.to(device), bs.to(device)).cpu().numpy().reshape(-1).astype(np.float32))
    return np.concatenate(scores), {"final_loss": float(losses[-1]), "losses": [float(v) for v in losses], "device": str(device)}


def metric_values(y_true: np.ndarray, score: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    y = y_true[mask]
    s = score[mask]
    out = {m: float("nan") for m in METRICS}
    if len(y) == 0 or int(y.sum()) == 0 or int((y == 0).sum()) == 0:
        return out
    out["average_precision"] = float(average_precision_score(y, s))
    out["roc_auc"] = float(roc_auc_score(y, s))
    pred = s >= np.nanmedian(s)
    out["balanced_accuracy"] = float(balanced_accuracy_score(y, pred))
    k = max(1, int(math.ceil(0.01 * len(y))))
    top = np.argsort(-s)[:k]
    out["recall_at_1pct"] = float(y[top].sum() / max(1, y.sum()))
    out["precision_at_1pct"] = float(y[top].mean())
    return out


def metrics_table(method_scores: Dict[str, np.ndarray], meta: pd.DataFrame, eval_idx: np.ndarray, target_col: str) -> pd.DataFrame:
    y = meta.loc[eval_idx, target_col].to_numpy(dtype=int)
    rows = []
    for method, scores in method_scores.items():
        vals = metric_values(y, scores[eval_idx])
        rows.append(
            {
                "method": method,
                "target": target_col.replace("label_", ""),
                "n_eval": int(len(eval_idx)),
                "n_positive": int(y.sum()),
                **vals,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(
    method_scores: Dict[str, np.ndarray],
    meta: pd.DataFrame,
    eval_idx: np.ndarray,
    target_col: str,
    n_boot: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    frame = meta.loc[eval_idx, ["run", target_col]].copy()
    frame["_idx"] = eval_idx
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    rows = []
    for method, scores in method_scores.items():
        boot_vals = {metric: [] for metric in METRICS}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            idx = np.concatenate([frame.loc[frame["run"] == run, "_idx"].to_numpy(dtype=int) for run in sampled])
            vals = metric_values(meta.loc[idx, target_col].to_numpy(dtype=int), scores[idx])
            for metric, value in vals.items():
                if np.isfinite(value):
                    boot_vals[metric].append(float(value))
        for metric, values in boot_vals.items():
            arr = np.asarray(values, dtype=float)
            rows.append(
                {
                    "method": method,
                    "target": target_col.replace("label_", ""),
                    "metric": metric,
                    "ci_low": float(np.quantile(arr, 0.025)) if len(arr) else float("nan"),
                    "ci_high": float(np.quantile(arr, 0.975)) if len(arr) else float("nan"),
                    "n_boot_valid": int(len(arr)),
                }
            )
    return pd.DataFrame(rows)


def per_run_metrics(method_scores: Dict[str, np.ndarray], meta: pd.DataFrame, eval_idx: np.ndarray, target_col: str) -> pd.DataFrame:
    rows = []
    for run in sorted(meta.loc[eval_idx, "run"].unique()):
        idx = eval_idx[meta.loc[eval_idx, "run"].to_numpy() == run]
        y = meta.loc[idx, target_col].to_numpy(dtype=int)
        for method, scores in method_scores.items():
            vals = metric_values(y, scores[idx])
            rows.append({"run": int(run), "method": method, "n_eval": int(len(idx)), "n_positive": int(y.sum()), **vals})
    return pd.DataFrame(rows)


def ci_string(ci: pd.DataFrame, method: str, metric: str) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty:
        return ""
    return "[{:.3g}, {:.3g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def write_report(
    out_dir: Path,
    config: dict,
    raw_root_dir: Path,
    counts: pd.DataFrame,
    p09c_counts: pd.DataFrame,
    expanded_counts: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    per_run: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
    model_info: dict,
    runtime: float,
) -> None:
    expected = int(load_json(Path(config["p09a_config"]))["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    view = metrics.copy()
    for metric in METRICS:
        view[metric + "_ci"] = [ci_string(ci, method, metric) for method in view["method"]]
    lines = [
        "# P09e: broad-mismatch low-positive audit",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Abstract",
        "P09c reported a suspiciously high recover/veto average precision for `novel_broad_template_mismatch`, but the decisive charge-outlier support came from a single held-out positive. This study re-runs the raw ROOT reproduction gate, recreates the P09c low-positive count, expands held-out coverage to eleven runs, and benchmarks a strong traditional score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a gated hybrid CNN+tabular architecture.",
        "",
        "## Raw reproduction",
        "The ROOT inputs were read from `{}`. The S00/P09a selection is even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC. This scan is executed before taxonomy, propagation labels, or model fitting.".format(raw_root_dir),
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} |".format(expected, reproduced, reproduced == expected),
        "",
        "## Label definitions",
        "Let \(x_i(t)\) be the 18-sample peak-normalized waveform for pulse \(i\). P09a broad candidates are the union of width-broad pulses and q-template-only pulses, where the thresholds are fitted only on non-held-out runs. Propagation sentinels are robust z scores fitted on the same train runs:",
        "",
        "\\[ z_f(i) = \\frac{f_i - \\operatorname{median}_{j \\in T} f_j}{1.4826\\operatorname{MAD}_{j \\in T}(f_j)}. \\]",
        "",
        "The primary endpoint is `broad_veto_like`: a broad candidate with at least one charge, baseline, pile-up, timing-tail, dropout, or saturation sentinel. The specific low-positive endpoint is `broad_charge_outlier`: a broad candidate with charge-area robust z above the train q99.5 threshold.",
        "",
        "## P09c low-positive reproduction",
        p09c_counts.to_markdown(index=False),
        "",
        "## Expanded held-out support",
        "The expanded split holds out runs `{}` and trains thresholds/models on all other configured B-stack runs.".format(
            ", ".join(str(r) for r in config["heldout_runs"])
        ),
        "",
        expanded_counts.to_markdown(index=False),
        "",
        "## Benchmark methods",
        "All models exclude run, event, stave, and source-index identifiers. Ridge and gradient-boosted trees use standardized scalar pulse-shape features. The MLP uses the same scalar features. The 1D-CNN uses only the normalized waveform. The new architecture is a gated hybrid: a waveform convolutional branch is multiplicatively gated by a scalar-feature branch before the final classifier. The traditional comparator is a frozen robust score combining q-template/width evidence with charge, baseline, pile-up, and duplicate timing sentinels.",
        "",
        "For held-out predictions \(s_i\), the primary ranking metric is average precision, with ROC-AUC, balanced accuracy at the median score, and top-1% recall/precision reported as diagnostics. CIs are bootstrap intervals over held-out runs, not row bootstraps.",
        "",
        "## Held-out benchmark",
        view.to_markdown(index=False),
        "",
        "## Per-run diagnostics",
        per_run.to_markdown(index=False),
        "",
        "## Leakage and systematics checks",
        leakage.to_markdown(index=False),
        "",
        "## Result",
        "The winner by primary average precision is `{}` with AP {:.4f} (95% run-bootstrap CI {}). The expanded charge-outlier count determines whether the P09c single-row support was a low-count artifact; the table above reports both the original four-run count and the expanded eleven-run count.".format(
            winner["method"], float(winner["average_precision"]), ci_string(ci, winner["method"], "average_precision")
        ),
        "",
        "## Caveats",
        "The propagation endpoints are deterministic audit labels, not new hand-scanned physics truth. Since charge, width, and timing quantities participate in both the labels and some tabular features, high tabular AP should be read as closure of the operational veto definition rather than proof of a new waveform class. The CNN-only comparator is a useful non-tabular stress test: if it wins, waveform morphology alone carries the endpoint; if it loses, the endpoint is mostly scalar-quality information. Bootstrap intervals cover run-to-run composition but not threshold-definition uncertainty outside the selected runs.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}` with Python `{}`. Torch device for neural models was `{}`. `manifest.json` records command, input, code, and output hashes.".format(
            runtime, platform.node(), platform.python_version(), model_info.get("torch_device", "cpu")
        ),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09e_1781032068_1446_13fd5bb1_broad_mismatch_low_positive_audit.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09a = load_module("p09a_rare_waveform_anomaly_taxonomy", Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py"))
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)
    waves, raw_meta, counts = p09a.scan_raw(p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(p09a_config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("Raw reproduction failed before model work: expected {}, got {}".format(expected, reproduced))

    p09c_meta, p09c_thresholds, p09c_prop_thresholds, _, p09c_heldout_mask = prepare_from_scan(
        p09a, p09a_config, waves, raw_meta, config["p09c_reference_heldout_runs"]
    )
    p09c_counts = pd.DataFrame(
        [
            {
                "scope": "p09c_reference_four_runs",
                "heldout_runs": ",".join(str(r) for r in config["p09c_reference_heldout_runs"]),
                "broad_candidates": int((p09c_heldout_mask & p09c_meta["label_gallery_qtemplate_or_broad"].to_numpy(bool)).sum()),
                "broad_veto_like": int((p09c_heldout_mask & p09c_meta["label_broad_veto_like"].to_numpy(bool)).sum()),
                "broad_charge_outlier": int((p09c_heldout_mask & p09c_meta["label_broad_charge_outlier"].to_numpy(bool)).sum()),
            }
        ]
    )
    p09c_counts.to_csv(out_dir / "p09c_low_positive_reproduction.csv", index=False)
    p09c_thresholds.to_csv(out_dir / "p09c_frozen_thresholds.csv", index=False)
    p09c_prop_thresholds.to_csv(out_dir / "p09c_propagation_thresholds.csv", index=False)

    meta, p09a_thresholds, prop_thresholds, train_mask, heldout_mask = prepare_from_scan(
        p09a, p09a_config, waves, raw_meta, config["heldout_runs"]
    )
    p09a_thresholds.to_csv(out_dir / "expanded_frozen_thresholds.csv", index=False)
    prop_thresholds.to_csv(out_dir / "expanded_propagation_thresholds.csv", index=False)
    label_counts = []
    for run, subset in meta.loc[heldout_mask].groupby("run", sort=True):
        label_counts.append(
            {
                "run": int(run),
                "heldout_rows": int(len(subset)),
                "broad_candidates": int(subset["label_gallery_qtemplate_or_broad"].sum()),
                "broad_veto_like": int(subset["label_broad_veto_like"].sum()),
                "broad_charge_outlier": int(subset["label_broad_charge_outlier"].sum()),
                "p09a_taxon_broad": int((subset["taxon"] == TARGET).sum()),
            }
        )
    expanded_counts = pd.DataFrame(label_counts)
    expanded_counts.to_csv(out_dir / "expanded_label_counts_by_run.csv", index=False)

    train_audit_idx = audit_indices(meta, train_mask, int(config["normal_ratio"]), rng)
    eval_idx = audit_indices(meta, heldout_mask, int(config["normal_ratio"]), rng)
    target_col = "label_" + str(config["primary_target"])
    y = meta[target_col].to_numpy(dtype=int)
    train_idx = balanced_train_indices(
        meta,
        train_audit_idx,
        target_col,
        int(config["train_negative_to_positive_ratio"]),
        int(config["torch"]["max_train_rows"]),
        rng,
    )

    scalar_frame, scalar_cols = scalar_feature_frame(meta)
    scalar_all = scalar_frame.to_numpy(dtype=np.float32)
    scalar_scaled, _ = standardize(train_idx, scalar_all)
    wave_scaled = waves.astype(np.float32)

    method_scores: Dict[str, np.ndarray] = {
        "traditional_robust_broad_veto": traditional_score(meta, train_mask),
        "ridge_scalar": fit_ridge(scalar_scaled, y, train_idx),
        "gradient_boosted_trees": fit_gbt(config, scalar_scaled, y, train_idx),
    }
    mlp_score, mlp_info = fit_torch_single_input(
        scalar_scaled, y, train_idx, "mlp", config, int(config["random_seed"]) + 51
    )
    cnn_score, cnn_info = fit_torch_single_input(
        wave_scaled, y, train_idx, "cnn", config, int(config["random_seed"]) + 59
    )
    hybrid_score, hybrid_info = fit_hybrid(wave_scaled, scalar_scaled, y, train_idx, config)
    method_scores["mlp_scalar_nn"] = mlp_score
    method_scores["cnn1d_waveform_nn"] = cnn_score
    method_scores["hybrid_gated_cnn_tabular"] = hybrid_score

    metrics = metrics_table(method_scores, meta, eval_idx, target_col)
    metrics.to_csv(out_dir / "benchmark_metrics.csv", index=False)
    ci = bootstrap_ci(method_scores, meta, eval_idx, target_col, int(config["bootstrap_replicates"]), rng)
    ci.to_csv(out_dir / "benchmark_run_bootstrap_ci.csv", index=False)
    per_run = per_run_metrics(method_scores, meta, eval_idx, target_col)
    per_run.to_csv(out_dir / "benchmark_per_run_metrics.csv", index=False)

    winner_row = metrics.sort_values(["average_precision", "roc_auc"], ascending=False).iloc[0].to_dict()
    top_rows = meta.loc[eval_idx, [
        "run",
        "event_index",
        "eventno",
        "evt",
        "stave",
        "taxon",
        "broad_source",
        "amplitude_adc",
        "q_template_rmse",
        "width_half",
        "area_norm",
        "charge_score",
        "baseline_score",
        "pileup_score",
        "timing_score",
        "label_broad_veto_like",
        "label_broad_charge_outlier",
    ]].copy()
    for method, score in method_scores.items():
        top_rows[method + "_score"] = normalize_score(score[eval_idx])
    top_rows = top_rows.sort_values(winner_row["method"] + "_score", ascending=False).head(300)
    top_rows.to_csv(out_dir / "top_heldout_rows_by_winner.csv", index=False)

    train_hashes = set(p09a.waveform_hashes(waves[train_idx]))
    eval_hashes = set(p09a.waveform_hashes(waves[eval_idx]))
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_models",
                "value": reproduced,
                "pass": bool(reproduced == expected),
                "note": "script raises before taxonomy/model work if this fails",
            },
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(meta.loc[train_mask, "run"]).intersection(set(config["heldout_runs"])))),
                "pass": True,
                "note": "all templates, thresholds, scalers, and models fit on non-held-out runs",
            },
            {
                "check": "identifier_features_used",
                "value": 0,
                "pass": True,
                "note": "run, event, eventno, evt, stave, and source index are excluded from model matrices",
            },
            {
                "check": "eval_waveform_hash_seen_in_train_rate",
                "value": float(len(train_hashes.intersection(eval_hashes)) / max(1, len(eval_hashes))),
                "pass": bool(len(train_hashes.intersection(eval_hashes)) == 0),
                "note": "rounded normalized waveform hashes at 1e-3 precision",
            },
            {
                "check": "p09c_charge_outlier_positive_count",
                "value": int(p09c_counts.iloc[0]["broad_charge_outlier"]),
                "pass": bool(int(p09c_counts.iloc[0]["broad_charge_outlier"]) <= 2),
                "note": "documents the original low-positive bottleneck rather than treating high AP as robust",
            },
            {
                "check": "expanded_charge_outlier_runs",
                "value": int((expanded_counts["broad_charge_outlier"] > 0).sum()),
                "pass": True,
                "note": "number of expanded held-out runs with at least one broad charge-outlier positive",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(p09a_config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [p09a_config_path, config_path, Path(config["p09c_reference_config"])]:
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    model_info = {
        "scalar_features": scalar_cols,
        "train_audit_rows": int(len(train_audit_idx)),
        "train_fit_rows": int(len(train_idx)),
        "train_fit_positives": int(y[train_idx].sum()),
        "eval_rows": int(len(eval_idx)),
        "eval_positives": int(y[eval_idx].sum()),
        "torch_device": hybrid_info.get("device", "cpu"),
        "mlp": mlp_info,
        "cnn1d": cnn_info,
        "hybrid_gated": hybrid_info,
    }
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": bool(reproduced == expected),
        },
        "p09c_low_positive_reproduction": p09c_counts.to_dict(orient="records"),
        "expanded_heldout_label_counts": expanded_counts.to_dict(orient="records"),
        "heldout_runs": [int(r) for r in config["heldout_runs"]],
        "primary_target": config["primary_target"],
        "winner": winner_row,
        "benchmark_metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "per_run_metrics": per_run.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "model_info": model_info,
        "follow_up_tickets": [
            {
                "title": "P09f blinded human review of expanded broad-charge outliers",
                "rationale": "P09e uses deterministic propagation labels; a small blinded waveform review of the expanded charge-outlier positives would separate detector-quality vetoes from visually genuine broad-template failures.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(
        out_dir,
        config,
        raw_root_dir,
        counts,
        p09c_counts,
        expanded_counts,
        metrics,
        ci,
        per_run,
        leakage,
        winner_row,
        model_info,
        time.time() - t0,
    )

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "{} scripts/p09e_1781032068_1446_13fd5bb1_broad_mismatch_low_positive_audit.py --config {}".format(
            sys.executable, config_path
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            "scripts/p09e_1781032068_1446_13fd5bb1_broad_mismatch_low_positive_audit.py": sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
            "scripts/p09a_rare_waveform_anomaly_taxonomy.py": sha256_file(Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py")),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
        "winner_method": winner_row["method"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner_row}, indent=2))


if __name__ == "__main__":
    main()
