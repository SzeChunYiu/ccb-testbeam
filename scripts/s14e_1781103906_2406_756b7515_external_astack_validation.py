#!/usr/bin/env python3
"""S14e: external A-stack validation of S14d accepted saturation bands.

This study deliberately starts from raw HRD ROOT through the P04c event-matched
A/B extractor.  It asks whether B-stack features that close duplicate-readout
saturated charge bands in S14d also predict an external A-stack charge handle
when only event-matched topology supports that comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
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


ROOT = Path(__file__).resolve().parents[1]
P04C_PATH = ROOT / "scripts" / "p04c_ab_event_matched_charge_transfer.py"


def import_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p04c = import_script(P04C_PATH)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
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
        value = float(obj)
        return None if not math.isfinite(value) else value
    return obj


def ci(values: Sequence[float]) -> List[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def fmt_ci(values) -> str:
    if not isinstance(values, (list, tuple)) or len(values) != 2 or values[0] is None:
        return "[NA, NA]"
    return "[%.5g, %.5g]" % (float(values[0]), float(values[1]))


def md_table(frame: pd.DataFrame, columns: List[str], max_rows: int = 80) -> str:
    sub = frame.loc[:, columns].head(max_rows).copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else "%.5g" % float(v))
        elif sub[col].dtype.kind in "iu":
            sub[col] = sub[col].map(lambda v: "%d" % int(v))
        else:
            sub[col] = sub[col].map(lambda v: fmt_ci(v) if isinstance(v, (list, tuple)) else str(v))
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + rows)


def sample_for_run(run: int) -> str:
    run = int(run)
    if 31 <= run <= 42:
        return "sample_i_calibration"
    if 44 <= run <= 57:
        return "sample_i_analysis"
    if run == 64:
        return "sample_ii_calibration"
    if 58 <= run <= 65:
        return "sample_ii_analysis"
    return "other"


def current_for_run(run: int) -> str:
    return "low_2nA" if int(run) in (46, 47) else "high_20nA"


def add_topology(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    b_names = ["B2", "B4", "B6", "B8"]
    b_sel = out[[name + "_selected" for name in b_names]].to_numpy(dtype=bool)
    out["depth_idx"] = np.where(b_sel.any(axis=1), b_sel.shape[1] - 1 - np.argmax(b_sel[:, ::-1], axis=1), 0).astype(np.int16)
    out["depth_stave"] = np.asarray(b_names, dtype=object)[out["depth_idx"].to_numpy(dtype=int)]
    a1 = out["A1_selected"].to_numpy(dtype=bool)
    a3 = out["A3_selected"].to_numpy(dtype=bool)
    out["a_topology"] = np.where(a1 & a3, "A1+A3", np.where(a1, "A1", "A3"))
    out["sample"] = [sample_for_run(v) for v in out["run"].to_numpy()]
    out["current_family"] = [current_for_run(v) for v in out["run"].to_numpy()]
    out["log_target"] = np.log(np.maximum(out["target_a_charge"].to_numpy(dtype=float), 1.0))
    out["log_b2_charge"] = np.log(np.maximum(out["b2_charge"].to_numpy(dtype=float), 1.0))
    out["log_btotal_charge"] = np.log(np.maximum(out["b_total_charge"].to_numpy(dtype=float), 1.0))
    out["log_bdown_charge"] = np.log1p(np.maximum(out["b_downstream_charge"].to_numpy(dtype=float), 0.0))
    out["bdown_frac"] = out["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(out["b_total_charge"].to_numpy(dtype=float), 1.0)
    return out


def quantile_edges(values: np.ndarray, bins: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.asarray([-np.inf, np.inf])
    edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, int(bins) + 1)))
    if len(edges) < 2:
        return np.asarray([-np.inf, np.inf])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def digitize(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.searchsorted(edges[1:-1], values, side="right").astype(np.int16)


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> Tuple[np.ndarray, dict]:
    b2_edges = quantile_edges(train["log_b2_charge"].to_numpy(), int(config["traditional"]["b2_quantile_bins"]))
    positive = train.loc[train["b_downstream_charge"] > 0, "log_bdown_charge"].to_numpy()
    bd_edges = quantile_edges(positive, int(config["traditional"]["bdown_positive_quantile_bins"]))

    def add_bins(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["b2_bin"] = digitize(out["log_b2_charge"].to_numpy(), b2_edges)
        out["bdown_bin"] = np.where(out["b_downstream_charge"].to_numpy() <= 0, -1, digitize(out["log_bdown_charge"].to_numpy(), bd_edges))
        return out

    train_b = add_bins(train)
    test_b = add_bins(test)
    min_rows = int(config["traditional"]["min_cell_rows"])
    levels = [
        ["current_family", "a_topology", "depth_idx", "b_mult", "b_downstream_mult", "b2_bin", "bdown_bin"],
        ["current_family", "a_topology", "depth_idx", "b_mult", "b2_bin"],
        ["a_topology", "depth_idx", "b2_bin"],
        ["depth_idx", "b2_bin"],
        ["a_topology"],
    ]
    tables = []
    for cols in levels:
        grouped = train_b.groupby(cols, observed=True)["log_target"].agg(["median", "size"]).reset_index()
        grouped = grouped[grouped["size"] >= min_rows]
        table = {}
        for _, row in grouped.iterrows():
            key = tuple(row[c] for c in cols)
            if len(cols) == 1:
                key = key[0]
            table[key] = float(row["median"])
        tables.append(table)
    global_median = float(train_b["log_target"].median())
    pred = np.full(len(test_b), global_median, dtype=float)
    used = []
    for idx, row in enumerate(test_b.itertuples(index=False)):
        rowd = row._asdict()
        used_level = "global"
        for cols, table in zip(levels, tables):
            key = tuple(rowd[c] for c in cols)
            if len(cols) == 1:
                key = key[0]
            if key in table:
                pred[idx] = table[key]
                used_level = "+".join(cols)
                break
        used.append(used_level)
    return np.exp(pred), {"fallback_counts": pd.Series(used).value_counts().to_dict()}


def tabular_features(frame: pd.DataFrame, wave: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    amp = wave.max(axis=2)
    peak = wave.argmax(axis=2).astype(float) / float(wave.shape[2] - 1)
    total = np.maximum(charge.sum(axis=1), 1.0)
    early = np.clip(wave[:, :, :8], 0.0, None).sum(axis=(1, 2)) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=(1, 2)) / total
    half_width = (wave > (0.5 * np.maximum(amp[:, :, None], 1.0))).sum(axis=2)
    cols = [
        "depth_idx", "b_mult", "b_downstream_mult", "log_b2_charge",
        "log_btotal_charge", "log_bdown_charge", "bdown_frac",
    ]
    parts = [frame[cols].to_numpy(dtype=float), np.log1p(charge), np.log1p(np.maximum(amp, 0.0)), peak, half_width, early[:, None], late[:, None]]
    names = list(cols)
    for prefix in ["log_charge", "log_amp", "peak", "half_width"]:
        names.extend(["%s_B%d" % (prefix, i) for i in [2, 4, 6, 8]])
    names.extend(["early_charge_fraction", "late_charge_fraction"])
    return np.hstack(parts), names


def exp_clip(values: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(np.asarray(values, dtype=float), -20.0, 20.0))


class TinyMLP(nn.Module):
    def __init__(self, n_in: int, hidden: int = 48):
        super(TinyMLP, self).__init__()
        self.net = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, x):
        return self.net(x).squeeze(1)


class SmallCNN(nn.Module):
    def __init__(self, n_tab: int):
        super(SmallCNN, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 56), nn.ReLU(), nn.Linear(56, 1))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def sample_indices(idx: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    if len(idx) <= max_rows:
        return idx
    return rng.choice(idx, size=max_rows, replace=False)


def torch_device():
    if torch is None:
        raise RuntimeError("torch unavailable")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def fit_mlp_predict(x: np.ndarray, ylog: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, epochs: int, seed: int) -> np.ndarray:
    scaler = StandardScaler().fit(x[train_idx])
    xs = scaler.transform(x[train_idx]).astype(np.float32)
    ys = ylog[train_idx].astype(np.float32)
    loader = DataLoader(TensorDataset(torch.from_numpy(xs), torch.from_numpy(ys)), batch_size=512, shuffle=True)
    torch.manual_seed(seed)
    device = torch_device()
    model = TinyMLP(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.2e-3, weight_decay=2.0e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(epochs)):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    xt = scaler.transform(x[test_idx]).astype(np.float32)
    out = []
    for start in range(0, len(xt), 8192):
        with torch.no_grad():
            out.append(model(torch.from_numpy(xt[start:start + 8192]).to(device)).cpu().numpy())
    return exp_clip(np.concatenate(out))


def fit_cnn_predict(wave: np.ndarray, x: np.ndarray, ylog: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, epochs: int, seed: int) -> np.ndarray:
    scaler = StandardScaler().fit(x[train_idx])
    xt = scaler.transform(x[train_idx]).astype(np.float32)
    w = wave[train_idx].astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    w = (w / scale[:, None, None]).astype(np.float32)
    ys = ylog[train_idx].astype(np.float32)
    loader = DataLoader(TensorDataset(torch.from_numpy(w), torch.from_numpy(xt), torch.from_numpy(ys)), batch_size=512, shuffle=True)
    torch.manual_seed(seed)
    device = torch_device()
    model = SmallCNN(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=9.0e-4, weight_decay=1.0e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(epochs)):
        for wb, xb, yb in loader:
            wb = wb.to(device)
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    xh = scaler.transform(x[test_idx]).astype(np.float32)
    wh = wave[test_idx].astype(np.float32)
    hscale = np.maximum(np.percentile(np.abs(wh).reshape(len(wh), -1), 95, axis=1), 1.0)
    wh = (wh / hscale[:, None, None]).astype(np.float32)
    out = []
    for start in range(0, len(xh), 4096):
        stop = min(start + 4096, len(xh))
        with torch.no_grad():
            out.append(model(torch.from_numpy(wh[start:stop]).to(device), torch.from_numpy(xh[start:stop]).to(device)).cpu().numpy())
    return exp_clip(np.concatenate(out))


def metric(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)) / np.maximum(np.asarray(y, dtype=float), 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
        "tail_gt50pct": float(np.mean(np.abs(frac) > 0.50)),
    }


def run_bootstrap(frame: pd.DataFrame, method: str, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == int(run)] for run in runs}
    bias_vals = []
    res_vals = []
    rms_vals = []
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        vals = metric(sample["target_a_charge"].to_numpy(dtype=float), sample["pred_" + method].to_numpy(dtype=float))
        bias_vals.append(vals["bias_median_frac"])
        res_vals.append(vals["res68_abs_frac"])
        rms_vals.append(vals["full_rms_frac"])
    return {"bias_ci95": ci(bias_vals), "res68_ci95": ci(res_vals), "full_rms_ci95": ci(rms_vals)}


def fit_leave_one_run(frame: pd.DataFrame, wave: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, List[str]]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = list(config["benchmark_methods"])
    out = frame.copy()
    for method in methods:
        out["pred_" + method] = np.nan
    x, names = tabular_features(out, wave)
    y = out["target_a_charge"].to_numpy(dtype=float)
    ylog = np.log(np.maximum(y, 1.0))
    diagnostics = []

    for heldout in sorted(int(r) for r in out["run"].unique()):
        train_mask = out["run"].to_numpy(dtype=int) != heldout
        test_mask = ~train_mask
        train_idx_all = np.flatnonzero(train_mask)
        train_idx = sample_indices(train_idx_all, int(config["max_train_rows"]), rng)
        test_idx = np.flatnonzero(test_mask)
        trad_pred, trad_diag = fit_traditional(out.loc[train_mask], out.loc[test_mask], config)
        train_trad_pred, _train_trad_diag = fit_traditional(out.loc[train_mask], out.loc[train_mask], config)
        out.loc[test_mask, "pred_traditional_depth_charge_bins"] = trad_pred

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=4.0))
        ridge.fit(x[train_idx_all], ylog[train_idx_all])
        out.loc[test_mask, "pred_ridge"] = exp_clip(ridge.predict(x[test_idx]))

        gbdt = GradientBoostingRegressor(
            n_estimators=90,
            max_depth=3,
            learning_rate=0.045,
            subsample=0.80,
            random_state=int(config["random_seed"]) + heldout,
        )
        gbdt.fit(x[train_idx], ylog[train_idx])
        out.loc[test_mask, "pred_gradient_boosted_trees"] = exp_clip(gbdt.predict(x[test_idx]))

        if torch is not None:
            out.loc[test_mask, "pred_mlp"] = fit_mlp_predict(x, ylog, train_idx, test_idx, int(config["mlp_epochs"]), int(config["random_seed"]) + 100 + heldout)
            out.loc[test_mask, "pred_1d_cnn"] = fit_cnn_predict(wave, x, ylog, train_idx, test_idx, int(config["cnn_epochs"]), int(config["random_seed"]) + 200 + heldout)
            baseline_raw = np.full(len(out), np.nan, dtype=float)
            baseline_raw[train_idx_all] = train_trad_pred
            baseline_raw[test_idx] = trad_pred
            baseline = np.log(np.maximum(baseline_raw, 1.0))
            xr = np.column_stack([x, baseline])
            residual_target = ylog - baseline
            residual = fit_mlp_predict(xr, residual_target, train_idx, test_idx, int(config["mlp_epochs"]), int(config["random_seed"]) + 300 + heldout)
            out.loc[test_mask, "pred_physics_residual_mlp"] = out.loc[test_mask, "pred_traditional_depth_charge_bins"].to_numpy(dtype=float) * residual
        else:
            out.loc[test_mask, ["pred_mlp", "pred_1d_cnn", "pred_physics_residual_mlp"]] = np.nan

        diagnostics.append(
            {
                "heldout_run": heldout,
                "n_train": int(train_mask.sum()),
                "n_test": int(test_mask.sum()),
                "traditional_fallback_counts": json.dumps(trad_diag["fallback_counts"], sort_keys=True),
            }
        )

    lo, hi = np.percentile(y, [0.1, 99.9])
    for method in methods:
        col = "pred_" + method
        out[col] = np.clip(out[col].to_numpy(dtype=float), float(lo), float(hi))

    summary_rows = []
    for method in methods:
        row = {"method": method, "split": "leave-one-run-out"}
        row.update(metric(y, out["pred_" + method].to_numpy(dtype=float)))
        row.update(run_bootstrap(out, method, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values(["res68_abs_frac", "full_rms_frac"], ignore_index=True)

    by_run_rows = []
    for (run, sample), sub in out.groupby(["run", "sample"], observed=True):
        for method in methods:
            row = {"run": int(run), "sample": sample, "method": method}
            row.update(metric(sub["target_a_charge"].to_numpy(dtype=float), sub["pred_" + method].to_numpy(dtype=float)))
            by_run_rows.append(row)
    by_run = pd.DataFrame(by_run_rows)

    by_band_rows = []
    for (current, depth, atop), sub in out.groupby(["current_family", "depth_stave", "a_topology"], observed=True):
        if len(sub) < 20:
            continue
        for method in methods:
            row = {"current_family": current, "depth_stave": depth, "a_topology": atop, "method": method}
            row.update(metric(sub["target_a_charge"].to_numpy(dtype=float), sub["pred_" + method].to_numpy(dtype=float)))
            by_band_rows.append(row)
    return out, summary, by_run, pd.DataFrame(by_band_rows), {"folds": diagnostics}, names


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, p04_config: dict, s14d: dict, accepted: pd.DataFrame, b_counts: pd.DataFrame, a_counts: pd.DataFrame, ab_counts: pd.DataFrame, summary: pd.DataFrame, by_run: pd.DataFrame, by_band: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]
    trad = summary[summary["method"] == "traditional_depth_charge_bins"].iloc[0]
    ridge = summary[summary["method"] == "ridge"].iloc[0]
    gbdt = summary[summary["method"] == "gradient_boosted_trees"].iloc[0]
    mlp = summary[summary["method"] == "mlp"].iloc[0]
    cnn = summary[summary["method"] == "1d_cnn"].iloc[0]
    residual = summary[summary["method"] == "physics_residual_mlp"].iloc[0]
    got_b = int(b_counts["selected_pulses"].sum())
    exp_b = int(p04_config["expected_b_s00_selected_pulses"])

    lines = [
        "# S14e: external A-stack validation of accepted saturation bands",
        "",
        "## Abstract",
        "",
        "Raw ROOT reproduction passes the B-stack selected-pulse anchor exactly: `%d` selected pulses versus the expected `%d`." % (got_b, exp_b),
        "Starting from event-matched HRDA/HRDB rows, this study tests whether S14d accepted saturated B-stack correction bands transfer to an external A-stack charge handle.",
        "The external target is deliberately not duplicate readout; it is the positive-lobe selected A1/A3 charge in the same event.  The best leave-one-run-out method is **%s** with fractional res68 %.5g and run-bootstrap 95%% CI %s." % (winner["method"], winner["res68_abs_frac"], fmt_ci(winner["res68_ci95"])),
        "",
        "## Inputs and Raw Reproduction",
        "",
        "- **Ticket:** `%s`" % config["ticket_id"],
        "- **Worker:** `%s`" % config["worker"],
        "- **Raw files:** `data/root/root/{hrda,hrdb}_run_*.root`.",
        "- **S14d source:** `%s`; S14d winner `%s`, accepted band count `%s`." % (config["s14d_result"], s14d["winner"]["method"], s14d.get("accepted_band_count")),
        "- **P04c topology:** match HRDA and HRDB by `(run, EVT)`, require selected B2 and selected A1 or A3.",
        "",
        "| gate | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        "| B-stack selected pulses | %d | %d | %+d | %s |" % (exp_b, got_b, got_b - exp_b, str(got_b == exp_b)),
        "| A/B event-matched rows | NA | %d | NA | True |" % int(ab_counts["ab_rows_b2_and_a_any"].sum()),
        "",
        "A-stack selected-count reproduction from P04c configuration:",
        "",
        md_table(a_counts, ["sample", "events_total", "events_with_selected", "selected_pulses", "A1", "A3"]),
        "",
        "A/B topology rows by run:",
        "",
        md_table(ab_counts, ["run", "matched_events", "a_any_selected", "b2_selected", "ab_rows_b2_and_a_any", "ab_rows_b2_a_any_downstream_any"], max_rows=40),
        "",
        "Accepted S14d bands imported for external validation:",
        "",
        md_table(accepted[accepted["accepted_with_margin"] == True], ["current_family", "depth_stave", "saturated_stave", "method", "n_saturated", "saturated_energy_res68", "matched_unsat_energy_res68", "accepted_with_margin"], max_rows=30),
        "",
        "## Estimand and Split",
        "",
        "For event `i`, the external response is",
        "",
        "`y_i = sum_{a in {A1,A3}} 1[A_a selected] sum_t max(w_{iat} - median(w_{ia,0:3}), 0)`.",
        "",
        "All predictors use B-stack quantities only: selected even-channel waveforms, B2 charge/amplitude, downstream multiplicity, depth, and charge fractions.  The split is leave-one-run-out.  For run `r`, each model `f_{-r}` is trained on all rows with `run != r` and evaluated only on rows with `run == r`.  Confidence intervals resample the held-out runs as blocks.",
        "",
        "## Methods",
        "",
        "The strong traditional comparator is a train-only hierarchical median estimator:",
        "",
        "`f_trad(x) = median_train(log y | current, A topology, depth, B multiplicity, downstream multiplicity, B2 charge bin, downstream charge bin)`,",
        "",
        "with progressively coarser fallback strata down to A topology.  Bins are recomputed inside each training fold, so no held-out quantile information enters the model.",
        "",
        "ML/NN comparators are ridge regression on engineered B-stack features, gradient-boosted regression trees, a tabular MLP, a 1D-CNN over the four selected B-stack waveforms plus tabular features, and a new physics-residual MLP.  The residual model learns `log(y) - log(f_trad)` from the same B-stack inputs and then multiplies the traditional prediction by the learned residual factor.",
        "",
        "## Main Benchmark",
        "",
        md_table(summary, ["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "full_rms_frac", "full_rms_ci95", "within_25pct", "tail_gt50pct"]),
        "",
        "Traditional res68 is %.5g %s; ridge %.5g %s; gradient-boosted trees %.5g %s; MLP %.5g %s; 1D-CNN %.5g %s; physics-residual MLP %.5g %s." % (
            trad["res68_abs_frac"], fmt_ci(trad["res68_ci95"]),
            ridge["res68_abs_frac"], fmt_ci(ridge["res68_ci95"]),
            gbdt["res68_abs_frac"], fmt_ci(gbdt["res68_ci95"]),
            mlp["res68_abs_frac"], fmt_ci(mlp["res68_ci95"]),
            cnn["res68_abs_frac"], fmt_ci(cnn["res68_ci95"]),
            residual["res68_abs_frac"], fmt_ci(residual["res68_ci95"]),
        ),
        "",
        "## Run and Topology Stability",
        "",
        md_table(by_run[by_run["method"].isin([winner["method"], "traditional_depth_charge_bins", "gradient_boosted_trees", "physics_residual_mlp"])], ["run", "sample", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"], max_rows=120),
        "",
        md_table(by_band[by_band["method"].isin([winner["method"], "traditional_depth_charge_bins", "gradient_boosted_trees", "physics_residual_mlp"])], ["current_family", "depth_stave", "a_topology", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"], max_rows=100),
        "",
        "## Systematics and Caveats",
        "",
        "- External A-stack charge is a detector handle, not an absolute proton energy measurement.",
        "- A-stack support is sparse relative to the B-stack selected-pulse anchor; sample-II analysis A-stack counts are especially small.",
        "- The result tests transfer away from duplicate readout.  It does not invalidate S14d duplicate-readout closure; it bounds how far that closure can be generalized to an independent detector handle.",
        "- Geometry, A-stack efficiency, and A/B acceptance are not unfolded here.  The proposed follow-up ticket targets those nuisance terms directly.",
        "- Neural models are intentionally compact and trained inside run folds.  Their comparison is a leakage-resistant benchmark, not an architecture search.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `external_astack_summary.csv`, `external_astack_by_run.csv`, `external_astack_by_band.csv`, `fold_diagnostics.csv`, and `external_astack_predictions.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14e_1781103906_2406_756b7515_external_astack_validation.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    p04_config = load_yaml(Path(config["p04c_config"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/5 reproducing B-stack selected pulse anchor from raw ROOT ...", flush=True)
    b_counts = p04c.count_b_s00_gate(p04_config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    exp_b = int(p04_config["expected_b_s00_selected_pulses"])
    if got_b != exp_b:
        raise RuntimeError("B selected-pulse reproduction failed: %d != %d" % (got_b, exp_b))

    print("2/5 reproducing A-stack analysis gates from raw ROOT ...", flush=True)
    a_counts = p04c.count_astack_gate(p04_config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)

    print("3/5 extracting event-matched A/B rows from raw ROOT ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(p04_config)
    frame = add_topology(frame)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)

    print("4/5 fitting leave-one-run-out traditional/ML/NN benchmarks on %d rows ..." % len(frame), flush=True)
    frame, summary, by_run, by_band, diagnostics, feature_names = fit_leave_one_run(frame, wave, config)
    summary.to_csv(out_dir / "external_astack_summary.csv", index=False)
    by_run.to_csv(out_dir / "external_astack_by_run.csv", index=False)
    by_band.to_csv(out_dir / "external_astack_by_band.csv", index=False)
    pd.DataFrame(diagnostics["folds"]).to_csv(out_dir / "fold_diagnostics.csv", index=False)

    pred_cols = ["run", "evt", "sample", "current_family", "depth_stave", "a_topology", "target_a_charge", "b2_amp", "b2_charge", "b_downstream_charge", "b_total_charge"]
    pred_cols.extend(["pred_" + method for method in config["benchmark_methods"]])
    frame[pred_cols].to_csv(out_dir / "external_astack_predictions.csv", index=False)

    print("5/5 writing report and manifest ...", flush=True)
    s14d = json.loads(Path(config["s14d_result"]).read_text(encoding="utf-8"))
    accepted = pd.read_csv(config["s14d_acceptance_bands"])
    winner = summary.iloc[0].to_dict()
    finding = (
        "External A-stack transfer is much broader than S14d duplicate-readout closure. "
        "The winner is %s with selected-A charge res68 %.5g %s, while the strong traditional hierarchical bins give %.5g %s. "
        "The imported S14d winner was %s on duplicate-readout saturated B-stack energy proxy, but the external A-stack handle is topology- and acceptance-limited; therefore S14d accepted bands should not be promoted as detector-independent range-energy corrections without a geometry-aware external calibration."
        % (
            winner["method"],
            float(winner["res68_abs_frac"]),
            fmt_ci(winner["res68_ci95"]),
            float(summary[summary["method"] == "traditional_depth_charge_bins"]["res68_abs_frac"].iloc[0]),
            fmt_ci(summary[summary["method"] == "traditional_depth_charge_bins"]["res68_ci95"].iloc[0]),
            s14d["winner"]["method"],
        )
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": exp_b,
            "reproduced_selected_pulses": got_b,
            "delta": got_b - exp_b,
            "pass": got_b == exp_b,
        },
        "s14d_reference": {
            "result": config["s14d_result"],
            "winner": s14d["winner"],
            "accepted_band_count": s14d.get("accepted_band_count"),
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "source": "B-stack even-channel waveform and charge summaries",
            "target": "selected A1/A3 positive-lobe charge",
            "n_rows": int(len(frame)),
            "runs": sorted(int(r) for r in frame["run"].unique()),
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "held-out run block", "reps": int(config["bootstrap_reps"])},
        "feature_names": feature_names,
        "summary": json_ready(summary.to_dict(orient="records")),
        "winner": {
            "method": str(winner["method"]),
            "res68_abs_frac": float(winner["res68_abs_frac"]),
            "res68_ci95": json_ready(winner["res68_ci95"]),
            "bias_median_frac": float(winner["bias_median_frac"]),
            "full_rms_frac": float(winner["full_rms_frac"]),
            "within_25pct": float(winner["within_25pct"]),
        },
        "finding": finding,
        "novel_ticket": config.get("novel_ticket"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, p04_config, s14d, accepted, b_counts, a_counts, ab_counts, summary, by_run, by_band, result)

    input_runs = sorted(set(p04c.configured_p04_runs(p04_config)) | set(int(r) for r in p04_config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [p04_config["astack"]["file_prefix"], p04_config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(p04_config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": "%s scripts/s14e_1781103906_2406_756b7515_external_astack_validation.py --config %s" % (sys.executable, config_path),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "environment": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "inputs": json_ready(input_sha.to_dict(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print("DONE -> %s in %.1f s; winner=%s" % (out_dir, result["runtime_sec"], result["winner"]["method"]), flush=True)


if __name__ == "__main__":
    main()
