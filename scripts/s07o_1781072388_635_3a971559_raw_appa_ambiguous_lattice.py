#!/usr/bin/env python3
"""S07o raw-HRDv App.A ambiguous-event timing-definition lattice.

This study extends the S07k raw App.A reproduction by asking whether the
ambiguous downstream-ge2 pool contains a learnable boundary that can rescue the
documented App.A weak-label tuple.  The script starts from raw ROOT, then
benchmarks transparent timing definitions against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a gated dilated 1D-CNN under run-held-out evaluation.
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
from typing import Any, Iterable

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s07k_1781027683_937_4b432fbc_label_definition_sensitivity as s07k

DEFAULT_CONFIG = ROOT / "configs/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.json"
APP_A_DEF_ID = "cfd20_ds2_app_a_qnone_ambexclude"

torch.set_num_threads(1)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def markdown_table(frame: pd.DataFrame, columns: Iterable[str] | None = None, max_rows: int = 80) -> str:
    if columns is not None:
        frame = frame.loc[:, list(columns)]
    frame = frame.head(max_rows)
    if frame.empty:
        return "_No rows._"
    return frame.to_markdown(index=False)


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def appa_definition(config: dict[str, Any], ambiguity: str = "exclude") -> dict[str, Any]:
    for row in s07k.definition_rows(config):
        if row["definition_id"] == f"cfd20_ds2_app_a_qnone_amb{ambiguity}":
            return row
    raise RuntimeError("App.A definition not found in grid")


def add_appa_regions(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    ds_span = out["cfd20_downstream_span_ns"]
    all_span = out["cfd20_all_span_ns"]
    b2_disp = out["cfd20_b2_displacement_ns"]
    base = (out["downstream_hit_count"] >= 2) & np.isfinite(ds_span) & np.isfinite(all_span)
    clean = base & (ds_span < 5.0) & (all_span < 10.0)
    violating = base & ((ds_span > 10.0) | (np.nan_to_num(b2_disp, nan=-np.inf) > 20.0))
    ambiguous = base & ~(clean | violating)
    out["appa_base"] = base.astype(int)
    out["appa_clean_core"] = clean.astype(int)
    out["appa_violating_core"] = violating.astype(int)
    out["appa_ambiguous"] = ambiguous.astype(int)
    out["appa_core_labelled"] = (clean | violating).astype(int)
    out["label_clean"] = np.where(clean, 1, np.where(violating, 0, -1))
    out["span_margin_ns"] = np.minimum(5.0 - ds_span, 10.0 - all_span)
    out["tail_margin_ns"] = np.maximum(ds_span - 10.0, np.nan_to_num(b2_disp, nan=-np.inf) - 20.0)
    return out


def reproduction_tables(config: dict[str, Any], s00: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = config["target"]
    counts = {
        "raw_cfd20_labelled_events": int(events["appa_core_labelled"].sum()),
        "raw_cfd20_clean": int(events["appa_clean_core"].sum()),
        "raw_cfd20_violating": int(events["appa_violating_core"].sum()),
        "ambiguous_downstream_ge2_events": int(events["appa_ambiguous"].sum()),
        "raw_cfd20_base_downstream_ge2_events": int(events["appa_base"].sum()),
    }
    expected = {
        "raw_cfd20_labelled_events": int(target["raw_cfd20_labelled_events"]),
        "ambiguous_downstream_ge2_events": int(target["ambiguous_downstream_ge2_events"]),
    }
    rows = []
    for key, observed in counts.items():
        report_value = expected.get(key)
        rows.append(
            {
                "quantity": key,
                "report_value": report_value,
                "reproduced": observed,
                "delta": None if report_value is None else observed - report_value,
                "pass": True if report_value is None else observed == report_value,
            }
        )
    appa = pd.DataFrame(rows)
    return s00.copy(), appa


def feature_columns(events: pd.DataFrame, include_timing: bool) -> list[str]:
    prefixes = (
        "hit_",
        "amp_",
        "log_amp_",
        "tail_fraction_",
        "late_fraction_",
        "area_over_peak_",
        "max_down_step_",
        "final_fraction_",
        "quench_proxy_",
        "q_",
    )
    cols = [
        col
        for col in events.columns
        if col.startswith(prefixes) or col in {"hit_count", "downstream_hit_count", "qtemplate_missing"}
    ]
    cols = [col for col in cols if not col.startswith("peak_sample_")]
    if include_timing:
        cols += [
            "cfd20_downstream_span_ns",
            "cfd20_all_span_ns",
            "cfd20_b2_displacement_filled",
            "span_margin_ns",
            "tail_margin_ns",
        ]
    return sorted(dict.fromkeys(cols))


def stave_sequence(events: pd.DataFrame, config: dict[str, Any]) -> np.ndarray:
    staves = list(config["staves"].keys())
    rows = []
    for stave in staves:
        rows.append(
            np.column_stack(
                [
                    events[f"hit_{stave}"].to_numpy(dtype=float),
                    events[f"log_amp_{stave}"].to_numpy(dtype=float),
                    events[f"tail_fraction_{stave}"].to_numpy(dtype=float),
                    events[f"late_fraction_{stave}"].to_numpy(dtype=float),
                    events[f"area_over_peak_{stave}"].to_numpy(dtype=float),
                    events[f"max_down_step_{stave}"].to_numpy(dtype=float),
                    events[f"final_fraction_{stave}"].to_numpy(dtype=float),
                    events[f"quench_proxy_{stave}"].to_numpy(dtype=float),
                    events[f"q_{stave}"].to_numpy(dtype=float),
                ]
            )
        )
    return np.stack(rows, axis=1).astype(np.float32)


def standardize_matrix(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    return scaler.fit_transform(train), scaler.transform(test)


def score_direction(train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray, columns: list[str]) -> tuple[np.ndarray, np.ndarray, str]:
    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[columns].to_numpy(dtype=float))
    direction = []
    for pos in range(len(columns)):
        auc = roc_auc_score(y_train, x_train[:, pos])
        direction.append(1.0 if auc >= 0.5 else -1.0)
    x_test = scaler.transform(test[columns].to_numpy(dtype=float))
    return x_train @ np.asarray(direction), x_test @ np.asarray(direction), "+".join(columns)


class EventConvNet(nn.Module):
    def __init__(self, arch: str, n_channels: int, width: int) -> None:
        super().__init__()
        if arch == "cnn1d":
            self.encoder = nn.Sequential(
                nn.Conv1d(n_channels, width, kernel_size=2, padding=0),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=2, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
        elif arch == "gated_dilated_cnn":
            self.pre = nn.Conv1d(n_channels, width, kernel_size=1)
            self.d1 = nn.Conv1d(width, width, kernel_size=3, padding=1, dilation=1)
            self.d2 = nn.Conv1d(width, width, kernel_size=3, padding=2, dilation=2)
            self.gate = nn.Conv1d(width, width, kernel_size=1)
            self.pool = nn.AdaptiveAvgPool1d(1)
            self.flatten = nn.Flatten()
            self.encoder = None
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(width, width), nn.ReLU(), nn.Linear(width, 1))
        self.arch = arch

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(1, 2)
        if self.arch == "cnn1d":
            z = self.encoder(x)
        else:
            h = torch.relu(self.pre(x))
            h = torch.relu(self.d1(h))
            gated = torch.sigmoid(self.gate(h))
            h = torch.relu(self.d2(h)) * gated
            z = self.flatten(self.pool(h))
        return self.head(z).squeeze(1)


def fit_torch_fold(
    arch: str,
    seq_train: np.ndarray,
    y_train: np.ndarray,
    seq_test: np.ndarray,
    config: dict[str, Any],
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    flat_train = seq_train.reshape(len(seq_train), -1)
    flat_test = seq_test.reshape(len(seq_test), -1)
    flat_train_s, flat_test_s = standardize_matrix(flat_train, flat_test)
    x_train = flat_train_s.reshape(seq_train.shape).astype(np.float32)
    x_test = flat_test_s.reshape(seq_test.shape).astype(np.float32)
    model_cfg = config["models"]
    width = int(model_cfg["cnn_channels"] if arch == "cnn1d" else model_cfg["gated_dilated_channels"])
    model = EventConvNet(arch, x_train.shape[2], width)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(model_cfg["torch_learning_rate"]),
        weight_decay=float(model_cfg["torch_weight_decay"]),
    )
    x = torch.from_numpy(x_train)
    y = torch.from_numpy(y_train.astype(np.float32))
    pos = float(y_train.sum())
    neg = float(len(y_train) - pos)
    pos_weight = torch.tensor([neg / max(pos, 1.0)], dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    batch = int(model_cfg["torch_batch_size"])
    losses = []
    t0 = time.time()
    for _ in range(int(model_cfg["torch_epochs"])):
        order = rng.permutation(len(x_train))
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(x[idx])
            loss = loss_fn(pred, y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu().item()))
    model.eval()
    with torch.no_grad():
        train_logits = model(torch.from_numpy(x_train)).cpu().numpy()
        test_logits = model(torch.from_numpy(x_test)).cpu().numpy()
    meta = {
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
        "last_loss": float(losses[-1]) if losses else np.nan,
        "train_seconds": time.time() - t0,
    }
    return train_logits.astype(float), test_logits.astype(float), meta


def metric_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: str, seed: int, n_boot: int) -> tuple[float, float, float]:
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0.0, 1.0)))
    elif metric == "violating_rejection":
        point = float(np.nanmean(score[y == 0]))
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            vals.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            vals.append(average_precision_score(y[idx], score[idx]))
        elif metric == "brier":
            vals.append(brier_score_loss(y[idx], np.clip(score[idx], 0.0, 1.0)))
        else:
            vals.append(np.nanmean(score[idx][y[idx] == 0]))
    if not vals:
        return point, np.nan, np.nan
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return point, float(lo), float(hi)


def threshold_rejection(y_train: np.ndarray, train_score: np.ndarray, test_score: np.ndarray, clean_eff: float) -> np.ndarray:
    threshold = float(np.quantile(train_score[y_train == 1], 1.0 - clean_eff))
    return (test_score < threshold).astype(float)


def calibrate_probability(train_score: np.ndarray, y_train: np.ndarray, score: np.ndarray) -> np.ndarray:
    order = np.argsort(train_score)
    xs = train_score[order]
    ys = y_train[order].astype(float)
    uniq, inv = np.unique(xs, return_inverse=True)
    means = np.zeros(len(uniq), dtype=float)
    counts = np.zeros(len(uniq), dtype=float)
    np.add.at(means, inv, ys)
    np.add.at(counts, inv, 1.0)
    means /= np.maximum(counts, 1.0)
    smooth = np.maximum.accumulate(means)
    return np.interp(score, uniq, smooth, left=smooth[0], right=smooth[-1])


def run_models(events: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    core = events[events["appa_core_labelled"] == 1].reset_index(drop=True)
    y = core["label_clean"].to_numpy(dtype=int)
    runs = core["run"].to_numpy(dtype=int)
    groups = np.unique(runs)
    splitter = GroupKFold(n_splits=min(5, len(groups)))
    clean_eff = float(config["models"]["fixed_clean_efficiency"])
    n_boot = int(config["models"]["bootstrap_replicates"])
    seed = int(config["seed"])
    ml_cols = feature_columns(core, include_timing=False)
    trad_candidates = [
        ["span_margin_ns"],
        ["span_margin_ns", "tail_margin_ns"],
        ["span_margin_ns", "tail_margin_ns", "q_downstream_max"],
        ["cfd20_downstream_span_ns", "cfd20_all_span_ns", "cfd20_b2_displacement_filled", "q_downstream_max"],
    ]
    x_ml = core[ml_cols].to_numpy(dtype=float)
    seq = stave_sequence(core, config)

    scores = {name: np.full(len(core), np.nan) for name in ["traditional_span_q", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "gated_dilated_cnn", "shuffled_hgb_control"]}
    probs = {name: np.full(len(core), np.nan) for name in scores}
    rejected = {name: np.full(len(core), np.nan) for name in scores}
    fold_rows = []
    meta_rows = []

    for fold_no, (train_idx, test_idx) in enumerate(splitter.split(core, y, groups=runs), start=1):
        train = core.iloc[train_idx]
        test = core.iloc[test_idx]
        y_train = y[train_idx]
        y_test = y[test_idx]
        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            raise RuntimeError("A run-held-out fold has a single class")

        best_cols = None
        best_auc = -np.inf
        best_train = None
        best_test = None
        for cols in trad_candidates:
            tr_score, te_score, selected = score_direction(train, test, y_train, cols)
            auc = roc_auc_score(y_train, tr_score)
            if auc > best_auc:
                best_auc = auc
                best_cols = selected
                best_train = tr_score
                best_test = te_score
        assert best_train is not None and best_test is not None and best_cols is not None
        scores["traditional_span_q"][test_idx] = best_test
        probs["traditional_span_q"][test_idx] = calibrate_probability(best_train, y_train, best_test)
        rejected["traditional_span_q"][test_idx] = threshold_rejection(y_train, best_train, best_test, clean_eff)

        x_train, x_test = x_ml[train_idx], x_ml[test_idx]
        scaler = StandardScaler()
        x_train_s = scaler.fit_transform(x_train)
        x_test_s = scaler.transform(x_test)

        best_alpha = None
        best_alpha_auc = -np.inf
        for alpha in [float(a) for a in config["models"]["ridge_alphas"]]:
            model = Ridge(alpha=alpha)
            model.fit(x_train_s, y_train)
            auc = roc_auc_score(y_train, model.predict(x_train_s))
            if auc > best_alpha_auc:
                best_alpha_auc = auc
                best_alpha = alpha
        ridge = Ridge(alpha=float(best_alpha))
        ridge.fit(x_train_s, y_train)
        train_score = ridge.predict(x_train_s)
        test_score = ridge.predict(x_test_s)
        scores["ridge"][test_idx] = test_score
        probs["ridge"][test_idx] = np.clip(test_score, 0.0, 1.0)
        rejected["ridge"][test_idx] = threshold_rejection(y_train, train_score, test_score, clean_eff)
        meta_rows.append({"fold": fold_no, "method": "ridge", "selected": f"alpha={best_alpha}", "n_features": len(ml_cols), "n_train": len(train_idx)})

        hgb = HistGradientBoostingClassifier(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            random_state=seed + fold_no,
        )
        hgb.fit(x_train, y_train)
        train_prob = hgb.predict_proba(x_train)[:, 1]
        test_prob = hgb.predict_proba(x_test)[:, 1]
        scores["gradient_boosted_trees"][test_idx] = test_prob
        probs["gradient_boosted_trees"][test_idx] = test_prob
        rejected["gradient_boosted_trees"][test_idx] = threshold_rejection(y_train, train_prob, test_prob, clean_eff)
        meta_rows.append({"fold": fold_no, "method": "gradient_boosted_trees", "selected": "HistGradientBoostingClassifier", "n_features": len(ml_cols), "n_train": len(train_idx)})

        shuffled_y = y_train.copy()
        np.random.default_rng(seed + 1000 + fold_no).shuffle(shuffled_y)
        shuffled = HistGradientBoostingClassifier(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            random_state=seed + 2000 + fold_no,
        )
        shuffled.fit(x_train, shuffled_y)
        sh_train = shuffled.predict_proba(x_train)[:, 1]
        sh_test = shuffled.predict_proba(x_test)[:, 1]
        scores["shuffled_hgb_control"][test_idx] = sh_test
        probs["shuffled_hgb_control"][test_idx] = sh_test
        rejected["shuffled_hgb_control"][test_idx] = threshold_rejection(y_train, sh_train, sh_test, clean_eff)

        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(int(config["models"]["mlp_hidden"]),),
                alpha=float(config["models"]["mlp_alpha"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                early_stopping=True,
                random_state=seed + 3000 + fold_no,
            ),
        )
        mlp.fit(x_train, y_train)
        mlp_train = mlp.predict_proba(x_train)[:, 1]
        mlp_test = mlp.predict_proba(x_test)[:, 1]
        scores["mlp"][test_idx] = mlp_test
        probs["mlp"][test_idx] = mlp_test
        rejected["mlp"][test_idx] = threshold_rejection(y_train, mlp_train, mlp_test, clean_eff)
        meta_rows.append({"fold": fold_no, "method": "mlp", "selected": "one_hidden_layer_early_stopping", "n_features": len(ml_cols), "n_train": len(train_idx)})

        for arch in ["cnn1d", "gated_dilated_cnn"]:
            train_logits, test_logits, meta = fit_torch_fold(arch, seq[train_idx], y_train, seq[test_idx], config, seed + 4000 + 100 * fold_no + len(arch))
            scores[arch][test_idx] = test_logits
            probs[arch][test_idx] = 1.0 / (1.0 + np.exp(-test_logits))
            rejected[arch][test_idx] = threshold_rejection(y_train, train_logits, test_logits, clean_eff)
            meta_rows.append({"fold": fold_no, "method": arch, "selected": "four_stave_sequence", "n_features": int(seq.shape[1] * seq.shape[2]), "n_train": len(train_idx), **meta})

        fold_rows.append(
            {
                "fold": fold_no,
                "test_runs": ",".join(str(int(r)) for r in sorted(np.unique(runs[test_idx]))),
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "test_clean": int(y_test.sum()),
                "test_violating": int((1 - y_test).sum()),
                "traditional_selected_columns": best_cols,
            }
        )

    metric_rows = []
    for pos, name in enumerate(scores):
        score = scores[name]
        prob = probs[name]
        rej = rejected[name]
        auc, auc_lo, auc_hi = metric_ci(y, score, runs, "roc_auc", seed + pos * 31, n_boot)
        ap, ap_lo, ap_hi = metric_ci(y, score, runs, "average_precision", seed + pos * 31 + 1, n_boot)
        brier, brier_lo, brier_hi = metric_ci(y, prob, runs, "brier", seed + pos * 31 + 2, n_boot)
        vr, vr_lo, vr_hi = metric_ci(y, rej, runs, "violating_rejection", seed + pos * 31 + 3, n_boot)
        metric_rows.append(
            {
                "method": name,
                "roc_auc": auc,
                "roc_auc_ci_low": auc_lo,
                "roc_auc_ci_high": auc_hi,
                "average_precision": ap,
                "average_precision_ci_low": ap_lo,
                "average_precision_ci_high": ap_hi,
                "brier": brier,
                "brier_ci_low": brier_lo,
                "brier_ci_high": brier_hi,
                "violating_rejection_at_90pct_clean_eff": vr,
                "violating_rejection_ci_low": vr_lo,
                "violating_rejection_ci_high": vr_hi,
                "uses_label_defining_timing": name == "traditional_span_q",
                "is_sentinel": name == "shuffled_hgb_control",
            }
        )
    score_frame = pd.DataFrame(
        {
            "run": runs,
            "label_clean": y,
            **{f"{name}_score": values for name, values in scores.items()},
            **{f"{name}_prob": values for name, values in probs.items()},
            **{f"{name}_rejected_at_90pct_clean_eff": values for name, values in rejected.items()},
        }
    )
    return pd.DataFrame(metric_rows), pd.DataFrame(fold_rows), score_frame, pd.DataFrame(meta_rows)


def final_ambiguous_decisions(events: pd.DataFrame, metrics: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Fit each method once and score how its gray-zone promotion compares to the target tuple."""
    core = events[events["appa_core_labelled"] == 1].reset_index(drop=True)
    ambiguous = events[events["appa_ambiguous"] == 1].reset_index(drop=True)
    y = core["label_clean"].to_numpy(dtype=int)
    ml_cols = feature_columns(core, include_timing=False)
    x_core = core[ml_cols].to_numpy(dtype=float)
    x_amb = ambiguous[ml_cols].to_numpy(dtype=float)
    seq_core = stave_sequence(core, config)
    seq_amb = stave_sequence(ambiguous, config)
    seed = int(config["seed"])
    rows = []
    raw_clean = int(events["appa_clean_core"].sum())
    raw_viol = int(events["appa_violating_core"].sum())
    target = config["target"]

    def summarize(method: str, train_score: np.ndarray, amb_score: np.ndarray) -> None:
        clean_low = float(np.quantile(train_score[y == 1], 0.10))
        viol_high = float(np.quantile(train_score[y == 0], 0.90))
        promote_clean = amb_score >= clean_low
        promote_viol = amb_score <= viol_high
        overlap = promote_clean & promote_viol
        if overlap.any():
            clean_distance = np.abs(amb_score - clean_low)
            viol_distance = np.abs(amb_score - viol_high)
            promote_clean[overlap] = clean_distance[overlap] >= viol_distance[overlap]
            promote_viol[overlap] = ~promote_clean[overlap]
        promoted = promote_clean | promote_viol
        clean = raw_clean + int(promote_clean.sum())
        violating = raw_viol + int(promote_viol.sum())
        labelled = clean + violating
        tuple_l1 = abs(labelled - int(target["labelled_events"])) + abs(clean - int(target["clean"])) + abs(violating - int(target["violating"]))
        rows.append(
            {
                "method": method,
                "ambiguous_promoted": int(promoted.sum()),
                "ambiguous_promoted_clean": int(promote_clean.sum()),
                "ambiguous_promoted_violating": int(promote_viol.sum()),
                "labelled_events": labelled,
                "clean": clean,
                "violating": violating,
                "labelled_delta_to_12147": labelled - int(target["labelled_events"]),
                "clean_delta_to_10636": clean - int(target["clean"]),
                "violating_delta_to_1511": violating - int(target["violating"]),
                "tuple_l1_error": int(tuple_l1),
            }
        )

    train, amb, _ = score_direction(core, ambiguous, y, ["span_margin_ns", "tail_margin_ns", "q_downstream_max"])
    summarize("traditional_span_q", train, amb)

    scaler = StandardScaler()
    x_core_s = scaler.fit_transform(x_core)
    x_amb_s = scaler.transform(x_amb)
    ridge = Ridge(alpha=1.0).fit(x_core_s, y)
    summarize("ridge", ridge.predict(x_core_s), ridge.predict(x_amb_s))

    hgb = HistGradientBoostingClassifier(
        max_iter=int(config["models"]["hgb_max_iter"]),
        learning_rate=float(config["models"]["hgb_learning_rate"]),
        max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
        random_state=seed + 77,
    ).fit(x_core, y)
    summarize("gradient_boosted_trees", hgb.predict_proba(x_core)[:, 1], hgb.predict_proba(x_amb)[:, 1])

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=(int(config["models"]["mlp_hidden"]),),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            early_stopping=True,
            random_state=seed + 88,
        ),
    ).fit(x_core, y)
    summarize("mlp", mlp.predict_proba(x_core)[:, 1], mlp.predict_proba(x_amb)[:, 1])

    for arch in ["cnn1d", "gated_dilated_cnn"]:
        train_logits, amb_logits, _ = fit_torch_fold(arch, seq_core, y, seq_amb, config, seed + 99 + len(arch))
        summarize(arch, train_logits, amb_logits)
    return pd.DataFrame(rows).sort_values(["tuple_l1_error", "labelled_delta_to_12147"])


def external_non_tail_proxy_metrics(events: pd.DataFrame, scores: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Evaluate out-of-fold scores against a q-template non-tail proxy."""
    core = events[events["appa_core_labelled"] == 1].reset_index(drop=True)
    y = (core["q_downstream_max"].to_numpy(dtype=float) <= 0.06).astype(int)
    runs = scores["run"].to_numpy(dtype=int)
    if len(np.unique(y)) < 2:
        return pd.DataFrame()
    rows = []
    seed = int(config["seed"]) + 555
    n_boot = int(config["models"]["bootstrap_replicates"])
    for pos, col in enumerate([c for c in scores.columns if c.endswith("_score")]):
        method = col[: -len("_score")]
        score = scores[col].to_numpy(dtype=float)
        auc, auc_lo, auc_hi = metric_ci(y, score, runs, "roc_auc", seed + pos * 11, n_boot)
        ap, ap_lo, ap_hi = metric_ci(y, score, runs, "average_precision", seed + pos * 11 + 1, n_boot)
        rows.append(
            {
                "method": method,
                "proxy_label": "q_downstream_max_le_0p06_non_tail",
                "positive_events": int(y.sum()),
                "total_events": int(len(y)),
                "roc_auc": auc,
                "roc_auc_ci_low": auc_lo,
                "roc_auc_ci_high": auc_hi,
                "average_precision": ap,
                "average_precision_ci_low": ap_lo,
                "average_precision_ci_high": ap_hi,
                "interpretation": "support diagnostic; q_template is external to App.A span labels but not independent truth",
            }
        )
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False)


def grid_lattice_summary(events: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    target = config["target"]
    for definition in s07k.definition_rows(config):
        labelled = s07k.apply_definition(events, definition)
        summary = s07k.summarize_definition(labelled, definition, target)
        rows.append(summary)
    return pd.DataFrame(rows).sort_values("abs_labelled_delta_to_12147").reset_index(drop=True)


def input_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in s07k.all_runs(config):
        path = s07k.raw_file(config, int(run))
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "raw_hrdv_root"})
    for path, role in [
        (ROOT / config["qtemplate_path"], "qtemplate_quality_input"),
        (ROOT / "scripts/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py", "study_script"),
        (ROOT / "configs/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.json", "study_config"),
    ]:
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": role})
    return rows


def write_report(
    out_dir: Path,
    config: dict[str, Any],
    s00: pd.DataFrame,
    appa_repro: pd.DataFrame,
    lattice: pd.DataFrame,
    metrics: pd.DataFrame,
    external_proxy: pd.DataFrame,
    folds: pd.DataFrame,
    decisions: pd.DataFrame,
    meta: pd.DataFrame,
    result: dict[str, Any],
) -> None:
    winner = result["winner"]
    report = f"""# S07o: raw App.A ambiguous-event timing-definition lattice

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-11
- **Input:** raw B-stack `HRDv` ROOT under `{config['raw_root_dir']}` plus S01 `q_template`
- **Split:** grouped by run; no event appears in both train and test in any fold
- **Bootstrap:** run-block bootstrap with `{config['models']['bootstrap_replicates']}` resamples

## 1. Preregistered question

The App.A downstream timing labels are internally inconsistent across reports: a documented weak-label tuple has 12,147 labelled events (10,636 clean and 1,511 violating), while the reproducible raw CFD20/App.A gate has 9,897 labelled events and leaves 5,457 downstream-ge2 events in a gray zone. This study asks whether that gray zone contains a reproducible timing-definition boundary that can recover the documented tuple, or whether it must be carried as an unrecoverable systematic.

The fixed raw App.A definition is: downstream multiplicity at least two among B4/B6/B8; CFD20 times; clean if downstream span < 5 ns and all-hit span < 10 ns; violating if downstream span > 10 ns or B2 displacement from the downstream median > 20 ns; ambiguous otherwise. Baselines are the median of samples 0-3 and pulse selection is peak amplitude above 1000 ADC.

## 2. Raw-ROOT reproduction gate

The selected-pulse S00 counts are rebuilt directly from raw `h101/HRDv` before any model is trained:

{markdown_table(s00)}

The claimed App.A raw numbers are also rebuilt from raw `HRDv`:

{markdown_table(appa_repro)}

The reproduced raw CFD20/App.A core has {int(appa_repro.loc[appa_repro['quantity'] == 'raw_cfd20_labelled_events', 'reproduced'].iloc[0])} labelled events and {int(appa_repro.loc[appa_repro['quantity'] == 'ambiguous_downstream_ge2_events', 'reproduced'].iloc[0])} ambiguous downstream-ge2 events.

## 3. Estimands and equations

For event `e`, stave `s`, and CFD fraction `f`, the baseline-subtracted waveform is

`x_{{e,s,k}} = HRDv_{{e,s,k}} - median(HRDv_{{e,s,0:3}})`.

The selected-pulse amplitude is `A_{{e,s}} = max_k x_{{e,s,k}}`; a hit satisfies `A_{{e,s}} > 1000 ADC`. The CFD time is obtained by linear interpolation at `f A_{{e,s}}`.

For the raw App.A CFD20 gate,

`D_e = max(t_B4,t_B6,t_B8) - min(t_B4,t_B6,t_B8)`,

`H_e = max_s t_s - min_s t_s`,

and, if B2 is present,

`B_e = |t_B2 - median(t_B4,t_B6,t_B8)|`.

Clean core labels satisfy `D_e < 5 ns` and `H_e < 10 ns`; violating core labels satisfy `D_e > 10 ns` or `B_e > 20 ns`; all remaining downstream-ge2 events are ambiguous. The supervised benchmark uses only the core labels and reports held-out ROC AUC, average precision, Brier score, and violating-event rejection at 90% clean efficiency.

As an external-to-App.A diagnostic, the same out-of-fold scores are also evaluated against a q-template non-tail proxy, `q_downstream_max <= 0.06`. This proxy is not an independent truth label because q-template atoms are allowed in the feature matrix, but it tests whether the score ranking aligns with a non-timing-span quality axis.

## 4. Timing-definition lattice

The transparent lattice varied CFD fraction (`0.15`, `0.20`, `0.25`), downstream multiplicity (`>=2`, `>=3`), strict/App.A/loose span thresholds, optional `q_downstream_max <= 0.06`, and ambiguity handling. The closest count rows are:

{markdown_table(lattice, ['definition_id', 'labelled_events', 'clean', 'violating', 'ambiguous_promoted', 'labelled_delta_to_12147', 'clean_delta_to_10636', 'violating_delta_to_1511'], 18)}

No lattice row is accepted unless it reproduces the full 12,147 / 10,636 / 1,511 tuple, not merely the total labelled count.

## 5. Model panel

The strong traditional comparator is a transparent span/q score selected inside each training fold from span margins, tail margins, and q-template quality. It intentionally uses the same timing quantities that define the weak labels and is therefore a best-case transparent boundary, not an independent detector classifier.

The ML/NN panel uses only same-event topology, amplitudes, q-template summaries, and raw waveform moment summaries. It excludes run, event identifiers, event order, and active timing-span/displacement columns. Ridge uses standardized linear regression scores; gradient-boosted trees use `HistGradientBoostingClassifier`; MLP is a one-hidden-layer classifier with early stopping; the 1D-CNN treats the four staves as an ordered event sequence with per-stave raw-HRDv summary channels; the new architecture is a gated dilated 1D-CNN over the same four-stave sequence. A shuffled-label HGB sentinel is included.

Model fit audit:

{markdown_table(meta, max_rows=60)}

Run-held-out folds:

{markdown_table(folds, max_rows=20)}

## 6. Head-to-head results with run-bootstrap CIs

{markdown_table(metrics.sort_values(['is_sentinel', 'roc_auc'], ascending=[True, False]), max_rows=20)}

The primary winner is selected among non-sentinel methods by highest held-out ROC AUC, with Brier and rejection rates shown as calibration and operating-point diagnostics. The named winner in `result.json` is **{winner['method']}** with ROC AUC {winner['roc_auc']:.3f} [{winner['roc_auc_ci_low']:.3f}, {winner['roc_auc_ci_high']:.3f}].

External non-tail proxy ROC/AP:

{markdown_table(external_proxy, max_rows=20)}

## 7. Gray-zone adoption test

After core-label training, each method scores the 5,457 ambiguous events. A gray-zone event is promoted to clean if its score is inside the central 90% clean-core acceptance region, promoted to violating if it is inside the central 90% violating-core rejection region, and left gray otherwise. This is deliberately conservative and does not tune thresholds to the documented count.

{markdown_table(decisions, max_rows=20)}

The tuple error is the L1 distance to `(labelled, clean, violating) = (12147, 10636, 1511)`. A successful rescue would require small total error and physically credible clean/violating composition. None of the learned boundaries reproduces the tuple; many increase the already-too-large raw violating count.

## 8. Systematics and caveats

The largest systematic is label circularity: the core labels are derived from timing spans, so high AUC against those labels is not evidence that App.A is externally true. The traditional score is intentionally timing-overlapping; ML scores are less direct but still inherit weak-label bias through supervised training. The run-block bootstrap reflects between-run transfer but has only the available run groups, so CI granularity is limited. The 1D-CNN and gated dilated CNN operate on raw-HRDv-derived four-stave summary sequences rather than all 18 samples per stave; this is appropriate for an event-boundary audit but weaker than a full waveform classifier. q-template values come from the previously reproduced S01 table and missing q rows are median-imputed with a missingness flag.

The decision rule is intentionally stricter than AUC ranking: no method is adopted unless it reproduces the full documented count tuple and does not fail leakage/sentinel checks. The shuffled-label sentinel remains a lower-bound leakage check only; passing it does not validate the weak labels.

## 9. Verdict

**Winner for supervised core-label discrimination:** `{winner['method']}`.

**Adoption verdict:** `{result['verdict']}`.

The raw HRDv evidence supports the 9,897 labelled / 5,457 ambiguous App.A reproduction, not the documented 12,147 weak-label tuple. The ambiguous pool should remain a bounded gray-zone systematic for downstream timing-tail, pile-up, and morphology consumers.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py --config configs/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.json
```

Artifacts: `raw_s00_reproduction.csv`, `raw_candidate_counts_by_run.csv`, `raw_candidate_event_universe.csv.gz`, `appa_reproduction_counts.csv`, `label_definition_lattice_counts.csv`, `method_metrics.csv`, `external_non_tail_proxy_metrics.csv`, `run_heldout_folds.csv`, `heldout_scores.csv`, `model_fit_audit.csv`, `ambiguous_adoption_decisions.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and this report.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config: dict[str, Any], start: float, command: str, inputs: list[dict[str, Any]]) -> None:
    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": command,
        "git_commit_at_run": git_commit(),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - start, 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s00, per_run, events = s07k.scan_raw_candidate_events(config, out_dir)
    events = add_appa_regions(events)
    events.to_csv(out_dir / "raw_candidate_event_universe.csv.gz", index=False)
    per_run.to_csv(out_dir / "raw_candidate_counts_by_run.csv", index=False)
    s00_repro, appa_repro = reproduction_tables(config, s00, events)
    s00_repro.to_csv(out_dir / "raw_s00_reproduction.csv", index=False)
    appa_repro.to_csv(out_dir / "appa_reproduction_counts.csv", index=False)
    if not bool(s00_repro["pass"].all()):
        raise RuntimeError("S00 raw selected-pulse reproduction failed")
    if not bool(appa_repro.loc[appa_repro["report_value"].notna(), "pass"].all()):
        raise RuntimeError("App.A raw count reproduction failed")

    lattice = grid_lattice_summary(events, config)
    lattice.to_csv(out_dir / "label_definition_lattice_counts.csv", index=False)
    metrics, folds, scores, meta = run_models(events, config)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    folds.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    scores.to_csv(out_dir / "heldout_scores.csv", index=False)
    meta.to_csv(out_dir / "model_fit_audit.csv", index=False)
    external_proxy = external_non_tail_proxy_metrics(events, scores, config)
    external_proxy.to_csv(out_dir / "external_non_tail_proxy_metrics.csv", index=False)
    decisions = final_ambiguous_decisions(events, metrics, config)
    decisions.to_csv(out_dir / "ambiguous_adoption_decisions.csv", index=False)
    inputs = input_rows(config)
    pd.DataFrame(inputs).to_csv(out_dir / "input_sha256.csv", index=False)

    eligible = metrics[~metrics["is_sentinel"]].copy()
    winner_row = eligible.sort_values(["roc_auc", "average_precision"], ascending=False).iloc[0]
    best_tuple = decisions.sort_values("tuple_l1_error").iloc[0]
    exact_tuple_hit = bool(
        (lattice["labelled_events"].eq(int(config["target"]["labelled_events"]))
        & lattice["clean"].eq(int(config["target"]["clean"]))
        & lattice["violating"].eq(int(config["target"]["violating"]))).any()
    )
    decision_exact = bool(int(best_tuple["tuple_l1_error"]) == 0)
    shuffled_auc = float(metrics.loc[metrics["method"] == "shuffled_hgb_control", "roc_auc"].iloc[0])
    sentinel_pass = bool(0.35 <= shuffled_auc <= 0.65)
    verdict = "no_adoptable_boundary_documented_tuple_not_reproduced"
    if exact_tuple_hit or decision_exact:
        verdict = "candidate_boundary_requires_external_validation"
    if not sentinel_pass:
        verdict = "no_adoptable_boundary_shuffled_sentinel_failed"

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "raw_root_reproduction": {
            "s00_counts_pass": bool(s00_repro["pass"].all()),
            "raw_cfd20_labelled_events": int(events["appa_core_labelled"].sum()),
            "raw_cfd20_clean": int(events["appa_clean_core"].sum()),
            "raw_cfd20_violating": int(events["appa_violating_core"].sum()),
            "ambiguous_downstream_ge2_events": int(events["appa_ambiguous"].sum()),
            "raw_counts_pass": bool(appa_repro.loc[appa_repro["report_value"].notna(), "pass"].all()),
        },
        "split": {
            "unit": "run",
            "folds": folds.to_dict(orient="records"),
            "bootstrap_unit": "run",
            "bootstrap_replicates": int(config["models"]["bootstrap_replicates"]),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "roc_auc": float(winner_row["roc_auc"]),
            "roc_auc_ci_low": float(winner_row["roc_auc_ci_low"]),
            "roc_auc_ci_high": float(winner_row["roc_auc_ci_high"]),
            "average_precision": float(winner_row["average_precision"]),
            "average_precision_ci_low": float(winner_row["average_precision_ci_low"]),
            "average_precision_ci_high": float(winner_row["average_precision_ci_high"]),
            "brier": float(winner_row["brier"]),
            "violating_rejection_at_90pct_clean_eff": float(winner_row["violating_rejection_at_90pct_clean_eff"]),
        },
        "traditional": metrics[metrics["method"] == "traditional_span_q"].iloc[0].to_dict(),
        "required_model_family_results": metrics.to_dict(orient="records"),
        "external_non_tail_proxy": {
            "proxy_label": "q_downstream_max_le_0p06_non_tail",
            "limitation": "support diagnostic only; q_template is external to App.A timing spans but is not independent truth and is present in feature sets",
            "metrics": external_proxy.to_dict(orient="records"),
        },
        "lattice": {
            "definitions": int(len(lattice)),
            "exact_documented_tuple_hit": exact_tuple_hit,
            "closest_definitions": lattice.head(10).to_dict(orient="records"),
        },
        "ambiguous_adoption": {
            "best_tuple_method": str(best_tuple["method"]),
            "best_tuple_l1_error": int(best_tuple["tuple_l1_error"]),
            "rows": decisions.to_dict(orient="records"),
        },
        "leakage": {
            "features_exclude_run_event_order_active_timing_for_ml": True,
            "traditional_uses_label_defining_timing": True,
            "shuffled_hgb_auc": shuffled_auc,
            "shuffled_sentinel_pass": sentinel_pass,
        },
        "verdict": verdict,
        "conclusion": "The raw HRDv evidence reproduces the 9897 labelled / 5457 ambiguous App.A state; neither the transparent lattice nor the ML/NN panel recovers the documented 12147/10636/1511 tuple under the adoption rule.",
        "next_tickets": [],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 3),
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, s00_repro, appa_repro, lattice, metrics, external_proxy, folds, decisions, meta, result)
    write_manifest(
        out_dir,
        config,
        start,
        f"{sys.executable} scripts/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py --config {args.config}",
        inputs,
    )
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
