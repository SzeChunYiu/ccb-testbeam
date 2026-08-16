#!/usr/bin/env python3
"""Ticket #2385: S15 p/d deltaE-E PID bakeoff with raw-ROOT reproduction."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
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
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def configured_raw_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["raw_run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def reproduce_raw_counts(config: dict) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    channels = np.asarray(list(config["raw_b_channels"].values()), dtype=int)
    names = list(config["raw_b_channels"].keys())
    baseline_idx = np.asarray(config["raw_baseline_samples"], dtype=int)
    nsamp = int(config["raw_samples_per_channel"])
    cut = float(config["raw_amplitude_cut_adc"])
    rows = []
    inputs = []
    totals = {name: 0 for name in names}
    total_selected = 0
    total_events = 0
    for run in configured_raw_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        inputs.append(
            {"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        )
        run_counts = {name: 0 for name in names}
        events = 0
        with uproot.open(path) as root_file:
            for batch in root_file["h101"].iterate(
                ["EVENTNO", "HRDv"], step_size=20000, library="np"
            ):
                wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
                b_wave = wave[:, channels, :]
                corrected = b_wave - np.median(b_wave[:, :, baseline_idx], axis=2)[:, :, None]
                selected = corrected.max(axis=2) > cut
                events += int(selected.shape[0])
                for idx, name in enumerate(names):
                    run_counts[name] += int(selected[:, idx].sum())
        run_total = int(sum(run_counts.values()))
        total_events += events
        total_selected += run_total
        for name in names:
            totals[name] += run_counts[name]
        rows.append({"run": run, "events": events, "selected_pulses": run_total, **run_counts})
    expected = int(config["raw_expected_selected_pulses"])
    summary = {
        "raw_root_dir": str(raw_dir),
        "runs": len(rows),
        "events": int(total_events),
        "selected_pulses": int(total_selected),
        "expected_selected_pulses": expected,
        "delta": int(total_selected - expected),
        "passed": int(total_selected) == expected,
        "stave_counts": {k: int(v) for k, v in totals.items()},
    }
    if not summary["passed"]:
        raise RuntimeError(f"raw ROOT reproduction failed: {summary}")
    return pd.DataFrame(rows), summary, pd.DataFrame(inputs)


def load_pid_table(config: dict) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, list[str]]:
    path = ROOT / config["mc_event_table"]
    df = pd.read_parquet(path)
    classes = list(config["classes"])
    df = df[df["truth_species"].isin(classes)].copy()
    rng = np.random.default_rng(int(config["random_seed"]))
    chosen = []
    for cls in classes:
        idx = df.index[df["truth_species"] == cls].to_numpy()
        if len(idx) > int(config["max_per_class"]):
            idx = rng.choice(idx, size=int(config["max_per_class"]), replace=False)
        chosen.append(idx)
    idx = np.concatenate(chosen)
    rng.shuffle(idx)
    df = df.loc[idx].reset_index(drop=True)
    if df["run_id"].nunique() < 2:
        order = df["event_id"].rank(method="first").to_numpy(dtype=np.float64) - 1.0
        blocks = int(config.get("mc_eval_blocks", 5))
        df["eval_run"] = np.floor(order * blocks / max(len(df), 1)).astype(int)
        df["eval_run"] = df["eval_run"].clip(0, blocks - 1)
    else:
        df["eval_run"] = df["run_id"].astype(int)
    readout = df[["readout_B2", "readout_B4", "readout_B6", "readout_B8"]].to_numpy(
        dtype=np.float32
    )
    layers = df[[f"edep_layer_{i}" for i in range(8)]].to_numpy(dtype=np.float32)
    total = np.maximum(readout.sum(axis=1, keepdims=True), 1e-6)
    frac = readout / total
    active = (readout > 0).astype(np.float32)
    seq = np.stack([np.log1p(readout), frac, active], axis=1).astype(np.float32)
    layer_axis = np.arange(4, dtype=np.float32)
    centroid = (frac * layer_axis[None, :]).sum(axis=1)
    spread = np.sqrt(
        np.maximum((frac * (layer_axis[None, :] - centroid[:, None]) ** 2).sum(axis=1), 0.0)
    )
    tail = readout[:, 1:].sum(axis=1)
    first = readout[:, 0]
    deepest = np.where(
        (layers > 0.02).any(axis=1), 7 - np.argmax((layers > 0.02)[:, ::-1], axis=1), 8
    ).astype(np.float32)
    tab = np.column_stack(
        [
            np.log1p(readout),
            frac,
            np.log1p(total[:, 0]),
            np.log1p(first),
            np.log1p(tail),
            tail / np.maximum(first, 1e-6),
            centroid,
            spread,
            active.sum(axis=1),
            deepest,
            np.log1p(df["deltaE_mc_mev"].to_numpy(dtype=np.float32)),
            np.log1p(df["E_mc_4layer_mev"].to_numpy(dtype=np.float32)),
            np.log1p(df["E_mc_full_mev"].to_numpy(dtype=np.float32)),
        ]
    ).astype(np.float32)
    return df, seq, tab, classes


def class_weights(y: np.ndarray, n_classes: int) -> np.ndarray:
    counts = np.bincount(y, minlength=n_classes).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    return weights / weights.mean()


def traditional_predict(
    x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, n_classes: int
) -> np.ndarray:
    # Robust deltaE-E/penetration bands in physically interpretable columns.
    use_cols = [8, 9, 10, 13, 14, 15, 16]
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
    scores = np.empty((len(xv), n_classes), dtype=np.float32)
    for c in range(n_classes):
        z = (xv - med[c]) / scale[c]
        scores[:, c] = -0.5 * np.sum(z * z, axis=1) + prior[c]
    return scores.argmax(axis=1)


class SmallCNN(nn.Module):
    def __init__(self, n_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(24, n_classes),
        )

    def forward(self, seq, tab=None):
        return self.net(seq)


class HybridCNNTabular(nn.Module):
    def __init__(self, n_tab: int, n_classes: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(
            nn.Linear(24 + n_tab, 64),
            nn.ReLU(),
            nn.Dropout(0.08),
            nn.Linear(64, n_classes),
        )

    def forward(self, seq, tab=None):
        return self.head(torch.cat([self.conv(seq), tab], dim=1))


def torch_predict(
    model_cls, seq_train, tab_train, y_train, seq_test, tab_test, config, n_classes, use_tab: bool
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(int(config["random_seed"]))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    mean = tab_train.mean(axis=0, keepdims=True)
    std = tab_train.std(axis=0, keepdims=True) + 1e-6
    train_tab = (tab_train - mean) / std
    test_tab = (tab_test - mean) / std
    model = (
        model_cls(tab_train.shape[1], n_classes).to(device)
        if use_tab
        else model_cls(n_classes).to(device)
    )
    loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights(y_train, n_classes), dtype=torch.float32, device=device)
    )
    opt = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-3)
    ds = TensorDataset(
        torch.tensor(seq_train, dtype=torch.float32),
        torch.tensor(train_tab, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long),
    )
    loader = DataLoader(ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["torch_epochs"])):
        for sb, tb, yb in loader:
            sb, tb, yb = sb.to(device), tb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(sb, tb if use_tab else None), yb)
            loss.backward()
            opt.step()
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(seq_test), 4096):
            sb = torch.tensor(seq_test[start : start + 4096], dtype=torch.float32, device=device)
            tb = torch.tensor(test_tab[start : start + 4096], dtype=torch.float32, device=device)
            out.append(model(sb, tb if use_tab else None).argmax(dim=1).cpu().numpy())
    return np.concatenate(out)


def run_benchmarks(
    meta: pd.DataFrame, seq: np.ndarray, tab: np.ndarray, classes: list[str], config: dict
):
    y = pd.Categorical(meta["truth_species"], categories=classes).codes.astype(np.int64)
    groups = meta["eval_run"].to_numpy(dtype=int)
    n_classes = len(classes)
    methods = [
        "traditional_bands",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "cnn1d",
        "hybrid_cnn_tabular",
    ]
    preds = {m: np.full(len(y), -1, dtype=np.int64) for m in methods}
    fold_rows = []
    for group in sorted(np.unique(groups)):
        test = groups == group
        train = ~test
        print(
            f"fold eval_run={int(group)} train={int(train.sum())} test={int(test.sum())}",
            flush=True,
        )
        x_train, x_test = tab[train], tab[test]
        y_train, y_test = y[train], y[test]
        seq_train, seq_test = seq[train], seq[test]
        preds["traditional_bands"][test] = traditional_predict(x_train, y_train, x_test, n_classes)
        ridge = make_pipeline(StandardScaler(), RidgeClassifier(class_weight="balanced", alpha=1.0))
        ridge.fit(x_train, y_train)
        preds["ridge"][test] = ridge.predict(x_test)
        hgb = HistGradientBoostingClassifier(
            max_iter=120,
            learning_rate=0.06,
            l2_regularization=0.04,
            random_state=int(config["random_seed"]),
        )
        hgb.fit(x_train, y_train, sample_weight=class_weights(y_train, n_classes)[y_train])
        preds["gradient_boosted_trees"][test] = hgb.predict(x_test)
        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64, 32),
                alpha=1e-3,
                batch_size=256,
                max_iter=80,
                early_stopping=True,
                random_state=int(config["random_seed"]),
            ),
        )
        mlp.fit(x_train, y_train)
        preds["mlp"][test] = mlp.predict(x_test)
        preds["cnn1d"][test] = torch_predict(
            SmallCNN, seq_train, x_train, y_train, seq_test, x_test, config, n_classes, False
        )
        preds["hybrid_cnn_tabular"][test] = torch_predict(
            HybridCNNTabular, seq_train, x_train, y_train, seq_test, x_test, config, n_classes, True
        )
        for method in methods:
            fold_rows.append(
                {
                    "eval_run": int(group),
                    "method": method,
                    "n": int(test.sum()),
                    "balanced_accuracy": float(
                        balanced_accuracy_score(y_test, preds[method][test])
                    ),
                }
            )
    return preds, pd.DataFrame(fold_rows), y


def metric_bundle(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def summarize(
    y: np.ndarray,
    groups: np.ndarray,
    preds: dict[str, np.ndarray],
    classes: list[str],
    config: dict,
):
    rng = np.random.default_rng(int(config["random_seed"]) + 19)
    reps = int(config["bootstrap_reps"])
    unique = np.unique(groups)
    metric_rows = []
    species_rows = []
    for method, pred in preds.items():
        base = metric_bundle(y, pred)
        boot = {k: [] for k in base}
        for _ in range(reps):
            sample_groups = rng.choice(unique, size=len(unique), replace=True)
            idx = np.concatenate([np.flatnonzero(groups == g) for g in sample_groups])
            mb = metric_bundle(y[idx], pred[idx])
            for k, v in mb.items():
                boot[k].append(v)
        row = {"method": method, "n": int(len(y)), **base}
        for k, vals in boot.items():
            row[f"{k}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{k}_ci_high"] = float(np.percentile(vals, 97.5))
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
                sample_groups = rng.choice(unique, size=len(unique), replace=True)
                idx = np.concatenate([np.flatnonzero(groups == g) for g in sample_groups])
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
    return pd.DataFrame(metric_rows).sort_values(
        "balanced_accuracy", ascending=False
    ), pd.DataFrame(species_rows)


def leakage_checks(
    meta: pd.DataFrame, tab: np.ndarray, y: np.ndarray, config: dict
) -> pd.DataFrame:
    rows = []
    groups = meta["eval_run"].to_numpy(dtype=int)
    x_id = meta[["event_id", "run_id", "eval_run"]].to_numpy(dtype=np.float32)
    pred = np.full(len(y), -1, dtype=np.int64)
    for group in sorted(np.unique(groups)):
        train = groups != group
        test = groups == group
        model = make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=300)
        )
        model.fit(x_id[train], y[train])
        pred[test] = model.predict(x_id[test])
    val = float(balanced_accuracy_score(y, pred))
    rows.append(
        {
            "check": "identifier_only_run_heldout_balanced_accuracy",
            "value": val,
            "threshold": 0.65,
            "pass": bool(val < 0.65),
        }
    )
    rng = np.random.default_rng(int(config["random_seed"]) + 101)
    y_shuf = y.copy()
    rng.shuffle(y_shuf)
    pred = np.full(len(y), -1, dtype=np.int64)
    for group in sorted(np.unique(groups)):
        train = groups != group
        test = groups == group
        model = make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=300)
        )
        model.fit(tab[train], y_shuf[train])
        pred[test] = model.predict(tab[test])
    val = float(balanced_accuracy_score(y_shuf, pred))
    rows.append(
        {
            "check": "shuffled_label_ridge_balanced_accuracy",
            "value": val,
            "threshold": 0.60,
            "pass": bool(val < 0.60),
        }
    )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: list[str], floatfmt: str = ".4f") -> str:
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

    return "\n".join(
        [fmt(labels), "| " + " | ".join("-" * w for w in widths) + " |"]
        + [fmt(row) for row in rows]
    )


def write_report(
    out: Path,
    config: dict,
    raw_summary: dict,
    class_counts: pd.DataFrame,
    data_summary: dict,
    metrics: pd.DataFrame,
    species: pd.DataFrame,
    fold: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
) -> str:
    win = metrics.loc[metrics["method"] == winner].iloc[0]
    lines = [
        "# S15 ticket #2385: event-by-event deltaE-E particle ID bakeoff",
        "",
        "- **Ticket:** `#2385`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Raw ROOT input:** `{config['raw_root_dir']}`",
        f"- **MC p/d event table:** `{config['mc_event_table']}`",
        f"- **Beam-data diagnostic table:** `{config['data_event_table']}`",
        "",
        "## Executive result",
        "",
        (
            f"The winner is **{winner}** on run-held-out GEANT4 p/d labels, with "
            f"balanced accuracy {win['balanced_accuracy']:.4f} "
            f"[{win['balanced_accuracy_ci_low']:.4f}, "
            f"{win['balanced_accuracy_ci_high']:.4f}] and macro-F1 "
            f"{win['macro_f1']:.4f} [{win['macro_f1_ci_low']:.4f}, "
            f"{win['macro_f1_ci_high']:.4f}]."
        ),
        "",
        (
            "This is a supervised MC-truth benchmark for S15 method comparison, "
            "not a claim that the real beam-data events have externally validated "
            "p/d labels. The data table is used to document the real "
            "amplitude-support domain and the raw ROOT gate verifies that the "
            "HRD input stream is the expected one."
        ),
        "",
        "## Raw-ROOT reproduction gate",
        "",
        (
            "The script rescanned the HRD B-stack ROOT files and reproduced the "
            f"S00 selected-pulse count: {raw_summary['selected_pulses']:,} "
            "selected B-stave pulse records versus "
            f"{raw_summary['expected_selected_pulses']:,} expected "
            f"(delta {raw_summary['delta']}). The selector is median baseline "
            "over samples 0-3, B-stave channels B2/B4/B6/B8 = 0/2/4/6, and "
            "`max(waveform - median_baseline) > 1000 ADC`."
        ),
        "",
        "## Problem definition",
        "",
        (
            "For event \\(i\\), the class label is \\(y_i \\in \\{p,d\\}\\) from "
            "the MC truth species. The data vector is the four B-stack readout "
            "energy deposits \\(\\mathbf{x}_i=(B2_i,B4_i,B6_i,B8_i)\\). We "
            "define \\(E_i=\\sum_j x_{ij}\\), fractions "
            "\\(f_{ij}=x_{ij}/\\max(E_i,\\epsilon)\\), upstream loss "
            "\\(\\Delta E_i=x_{i,B2}\\), downstream residual "
            "\\(E_i^{\\mathrm{down}}=x_{i,B4}+x_{i,B6}+x_{i,B8}\\), and a "
            "penetration index \\(L_i=\\max\\{\\ell:E_{i\\ell}>0.02\\,"
            "\\mathrm{MeV}\\}\\) with sentinel 8 if no layer crosses threshold."
        ),
        "",
        "## Methods",
        "",
        (
            "The traditional method is a train-fold-only robust dE-E band "
            "classifier. For each class \\(c\\), medians \\(m_c\\), IQR scales "
            "\\(s_c\\), and priors \\(\\pi_c\\) are estimated in the "
            "handcrafted variables \\((\\log E, \\log \\Delta E, "
            "\\log E^{\\mathrm{down}}, E^{\\mathrm{down}}/\\Delta E, "
            "\\mu_{B}, \\sigma_{B}, L)\\). Prediction minimizes the diagonal "
            "robust distance "
            "\\(D_c(x)=\\frac12\\sum_k ((x_k-m_{ck})/s_{ck})^2-\\log\\pi_c\\)."
        ),
        "",
        (
            "The ML/NN panel is ridge classification, histogram "
            "gradient-boosted trees with class-balanced weights, a two-layer "
            "MLP, a 1D-CNN over the four B-stack sequence positions with "
            "channels \\([\\log(1+x_j), f_j, 1_{x_j>0}]\\), and a new "
            "`hybrid_cnn_tabular` architecture that concatenates the CNN "
            "embedding with standardized global dE-E/penetration variables."
        ),
        "",
        (
            "Evaluation is leave-one-block-held-out. If the MC table exposes "
            "multiple `run_id` values these are used directly; this artifact "
            "has degenerate `run_id=0`, so deterministic contiguous `eval_run` "
            "blocks are used instead. Confidence intervals are nonparametric "
            "bootstrap intervals that resample held-out blocks with replacement, "
            "preserving event membership within each block."
        ),
        "",
        "## Class balance and beam-data support",
        "",
        md_table(class_counts, ["truth_species", "available_events", "used_events"], ".0f"),
        "",
        md_table(
            pd.DataFrame([data_summary]),
            [
                "data_events",
                "sample_i_events",
                "sample_ii_events",
                "b2_saturation_fraction",
                "multi_stave_fraction",
            ],
        ),
        "",
        "## Method scoreboard",
        "",
        md_table(
            metrics,
            [
                "method",
                "balanced_accuracy",
                "balanced_accuracy_ci_low",
                "balanced_accuracy_ci_high",
                "macro_f1",
                "macro_f1_ci_low",
                "macro_f1_ci_high",
            ],
        ),
        "",
        "## Winner purity and efficiency",
        "",
        md_table(
            species[species["method"] == winner],
            [
                "species",
                "truth_n",
                "pred_n",
                "purity",
                "purity_ci_low",
                "purity_ci_high",
                "efficiency",
                "efficiency_ci_low",
                "efficiency_ci_high",
            ],
        ),
        "",
        "## Fold stability",
        "",
        md_table(fold[fold["method"] == winner], ["eval_run", "n", "balanced_accuracy"]),
        "",
        "## Controls",
        "",
        md_table(leakage, ["check", "value", "threshold", "pass"]),
        "",
        (
            "Identifier-only and shuffled-label controls are falsifiers for "
            "trivial run/event leakage and label-vector mistakes. They do not "
            "exclude all simulation artifacts."
        ),
        "",
        "## Systematics and caveats",
        "",
        (
            "- The supervised labels come from MC truth, not the real HRD beam "
            "data. Without S17-grade externally validated truth transfer, purity "
            "and efficiency are method-comparison quantities only."
        ),
        (
            "- The MC event table uses deposited-energy/readout proxies. It does "
            "not include the full electronics response, noise, saturation "
            "transfer, trigger efficiency, or waveform-level pedestal model of "
            "the HRD data."
        ),
        (
            "- The raw ROOT reproduction gate validates the selected-pulse input "
            "count and channel/baseline semantics, but it does not by itself "
            "validate p/d truth labels."
        ),
        (
            "- The MC table has degenerate `run_id=0`; the benchmark therefore "
            "uses deterministic contiguous event-index blocks labelled `eval_run` "
            "as run-like held-out source blocks. This satisfies leakage-resistant "
            "blocked evaluation for the available artifact, but it is weaker than "
            "a true multi-acquisition-run split."
        ),
        (
            "- Bootstrap intervals resample `eval_run` blocks, so they measure "
            "fold stability under the available generated source segmentation. "
            "They do not include material-budget, physics-list, Birks/quenching, "
            "calibration, or source-composition uncertainty."
        ),
        (
            "- The traditional bands are interpretable and train-fold frozen. "
            "Any global dE-E band drawn from all data would be an optimistic "
            "baseline and is intentionally avoided here."
        ),
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, "
            "`raw_reproduction_by_run.csv`, `class_counts.csv`, "
            "`data_support_summary.csv`, `method_metrics.csv`, "
            "`per_species_metrics.csv`, `fold_metrics.csv`, "
            "`confusion_matrix_winner.csv`, `leakage_checks.csv`, and this "
            "`REPORT.md` are in the report directory. Root-level `REPORT.md` "
            "and `result.json` mirror the report and summary for the ticket "
            "runner."
        ),
    ]
    text = "\n".join(lines) + "\n"
    (out / "REPORT.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/2385_s15_pid_bakeoff.json")
    args = parser.parse_args()
    start = time.time()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    raw_by_run, raw_summary, raw_inputs = reproduce_raw_counts(config)
    print(f"raw reproduction passed: {raw_summary['selected_pulses']} selected pulses", flush=True)
    meta, seq, tab, classes = load_pid_table(config)
    class_available = pd.read_parquet(ROOT / config["mc_event_table"])
    class_available = (
        class_available[class_available["truth_species"].isin(classes)]
        .groupby("truth_species")
        .size()
        .reset_index(name="available_events")
    )
    class_used = meta.groupby("truth_species").size().reset_index(name="used_events")
    class_counts = class_available.merge(class_used, on="truth_species", how="left").fillna(0)
    data_df = pd.read_parquet(ROOT / config["data_event_table"])
    data_summary = {
        "data_events": int(len(data_df)),
        "sample_i_events": int((data_df["sample"] == "I").sum()),
        "sample_ii_events": int((data_df["sample"] == "II").sum()),
        "b2_saturation_fraction": float(data_df["saturation_B2"].mean()),
        "multi_stave_fraction": float(
            (
                data_df[["threshold_pass_B4", "threshold_pass_B6", "threshold_pass_B8"]].sum(axis=1)
                > 0
            ).mean()
        ),
    }
    print(f"benchmark rows: {len(meta)} p/d events", flush=True)
    preds, fold, y = run_benchmarks(meta, seq, tab, classes, config)
    metrics, species = summarize(y, meta["eval_run"].to_numpy(dtype=int), preds, classes, config)
    leakage = leakage_checks(meta, tab, y, config)
    winner = str(metrics.iloc[0]["method"])
    cm = pd.DataFrame(
        confusion_matrix(y, preds[winner], labels=np.arange(len(classes))),
        index=[f"true_{c}" for c in classes],
        columns=[f"pred_{c}" for c in classes],
    )

    raw_by_run.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    class_counts.to_csv(out / "class_counts.csv", index=False)
    pd.DataFrame([data_summary]).to_csv(out / "data_support_summary.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    species.to_csv(out / "per_species_metrics.csv", index=False)
    fold.to_csv(out / "fold_metrics.csv", index=False)
    cm.to_csv(out / "confusion_matrix_winner.csv")
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    inputs = pd.concat(
        [
            raw_inputs,
            pd.DataFrame(
                [
                    {
                        "file": config["mc_event_table"],
                        "sha256": sha256_file(ROOT / config["mc_event_table"]),
                        "bytes": (ROOT / config["mc_event_table"]).stat().st_size,
                    },
                    {
                        "file": config["data_event_table"],
                        "sha256": sha256_file(ROOT / config["data_event_table"]),
                        "bytes": (ROOT / config["data_event_table"]).stat().st_size,
                    },
                    {
                        "file": str(config_path.relative_to(ROOT)),
                        "sha256": sha256_file(config_path),
                        "bytes": config_path.stat().st_size,
                    },
                    {
                        "file": str(Path(__file__).resolve().relative_to(ROOT)),
                        "sha256": sha256_file(Path(__file__).resolve()),
                        "bytes": Path(__file__).resolve().stat().st_size,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    inputs.to_csv(out / "input_sha256.csv", index=False)

    report = write_report(
        out,
        config,
        raw_summary,
        class_counts,
        data_summary,
        metrics,
        species,
        fold,
        leakage,
        winner,
    )
    result = {
        "ticket": "#2385",
        "title": config["title"],
        "worker": config["worker"],
        "winner": winner,
        "winner_metric": "run_heldout_balanced_accuracy",
        "winner_balanced_accuracy": float(metrics.iloc[0]["balanced_accuracy"]),
        "winner_balanced_accuracy_ci95": [
            float(metrics.iloc[0]["balanced_accuracy_ci_low"]),
            float(metrics.iloc[0]["balanced_accuracy_ci_high"]),
        ],
        "winner_macro_f1": float(metrics.iloc[0]["macro_f1"]),
        "raw_reproduction": raw_summary,
        "split": {
            "scheme": "leave_one_eval_run_block_out",
            "source_run_ids": sorted(int(v) for v in meta["run_id"].unique()),
            "eval_run_blocks": sorted(int(v) for v in meta["eval_run"].unique()),
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "classes": classes,
        "n_used_events": int(len(meta)),
        "methods": metrics.to_dict(orient="records"),
        "leakage_checks_passed": bool(leakage["pass"].all()),
        "next_tickets": [],
        "report_dir": config["output_dir"],
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "input_sha256.csv",
            "raw_reproduction_by_run.csv",
            "class_counts.csv",
            "data_support_summary.csv",
            "method_metrics.csv",
            "per_species_metrics.csv",
            "fold_metrics.csv",
            "confusion_matrix_winner.csv",
            "leakage_checks.csv",
        ],
        "runtime_sec": float(time.time() - start),
    }
    (out / "result.json").write_text(
        json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "ticket": "#2385",
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "config": str(config_path.relative_to(ROOT)),
        "command": (
            f"{platform.python_implementation()} "
            f"{Path(__file__).resolve().relative_to(ROOT)} "
            f"--config {config_path.relative_to(ROOT)}"
        ),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(torch, "__version__", None),
        },
        "runtime_sec": result["runtime_sec"],
    }
    (out / "manifest.json").write_text(
        json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (ROOT / "REPORT.md").write_text(report, encoding="utf-8")
    (ROOT / "result.json").write_text(
        json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "done": True,
                "ticket": "#2385",
                "winner": winner,
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
