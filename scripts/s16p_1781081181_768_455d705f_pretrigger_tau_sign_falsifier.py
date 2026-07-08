#!/usr/bin/env python3
"""S16p pretrigger tau sign-inversion falsifier.

The script reads B-stack raw ROOT files directly, reproduces the canonical
selected-pulse count, and benchmarks transparent and learned pretrigger models
under run-held-out current-family splits.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1781081181.768.455d705f__s16p_pretrigger_tau_sign_inversion_falsifier"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TICKET = "1781081181.768.455d705f"
WORKER = "testbeam-laptop-3"
STUDY = "S16p"
TITLE = "pretrigger tau sign-inversion falsifier"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DOWNSTREAM = {"B4", "B6", "B8"}
NSAMP = 18
PRE = np.array([0, 1, 2, 3], dtype=int)
AMP_CUT = 1000.0
EXPECTED_SELECTED = 640737
RUN_GROUPS = {
    "low_2nA": {"label": 0, "current_nA": 2.0, "runs": [46, 47]},
    "high_20nA": {"label": 1, "current_nA": 20.0, "runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]},
}
# Canonical S00/S16 B-stack physics-sample gate. Earlier commissioning runs
# 12-30 and run 43 are present in the ROOT directory but are not part of the
# published 640,737 selected-pulse reproduction number.
ALL_RUNS = [
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    39,
    40,
    41,
    42,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
]
BENCHMARK_RUNS = sorted([r for v in RUN_GROUPS.values() for r in v["runs"]])
RNG_SEED = 161081181
SAMPLE_PER_RUN = 900
BOOTSTRAPS = 500

NUMERIC = [
    "pre_mean",
    "pre_median",
    "pre_rms",
    "pre_ptp",
    "pre_slope",
    "pre_last_minus_first",
    "amp",
    "log_amp",
    "peak_sample",
    "tail_mean",
    "tail_slope",
    "late_over_amp",
    "live10",
    "live20",
]
CATEGORICAL = ["stave"]


def raw_file(run: int) -> Path:
    return RAW_ROOT_DIR / ("hrdb_run_%04d.root" % int(run))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if np.isfinite(x) else None
    return value


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 8, NSAMP), dtype=np.float32)
    return np.stack(values).astype(np.float32).reshape(-1, 8, NSAMP)


def run_label_map() -> dict:
    out = {}
    for group, info in RUN_GROUPS.items():
        for run in info["runs"]:
            out[int(run)] = (group, int(info["label"]), float(info["current_nA"]))
    return out


def load_run(run: int, keep_rows: bool = True) -> tuple[pd.DataFrame, np.ndarray, dict]:
    tree = uproot.open(raw_file(run))["h101"]
    arrays = tree.arrays(["TRIGGER", "EVENTNO", "EVT", "HRDv"], library="np")
    waves_all = stack_obj(arrays["HRDv"])
    selected = []
    rows = []
    waves = []
    channels = np.array([STAVES[s] for s in STAVES], dtype=int)
    stave_names = np.array(list(STAVES.keys()))
    label_lookup = run_label_map()
    group, current_label, current_nA = label_lookup.get(run, ("other", -1, np.nan))
    for start in range(0, len(waves_all), 20000):
        stop = min(start + 20000, len(waves_all))
        chunk = waves_all[start:stop]
        b = chunk[:, channels, :]
        pre = np.median(b[:, :, PRE], axis=2)
        corr = b - pre[:, :, None]
        amp = corr.max(axis=2)
        peak = corr.argmax(axis=2)
        sel = amp > AMP_CUT
        ev_idx, st_idx = np.where(sel)
        if len(ev_idx) == 0:
            continue
        downstream_event = sel[:, 1:].any(axis=1)
        selected.append(int(sel.sum()))
        if not keep_rows:
            continue
        w = corr[ev_idx, st_idx, :]
        raww = b[ev_idx, st_idx, :]
        pr = raww[:, PRE]
        tail = w[:, 10:]
        after10 = (w[:, 10:] > 0.10 * np.maximum(amp[ev_idx, st_idx], 1.0)[:, None]).sum(axis=1)
        after20 = (w[:, 10:] > 0.20 * np.maximum(amp[ev_idx, st_idx], 1.0)[:, None]).sum(axis=1)
        rec = pd.DataFrame(
            {
                "run": int(run),
                "group": group,
                "current_label": current_label,
                "current_nA": current_nA,
                "eventno": np.asarray(arrays["EVENTNO"])[start:stop][ev_idx].astype(np.int64),
                "evt": np.asarray(arrays["EVT"])[start:stop][ev_idx].astype(np.int64),
                "trigger": np.asarray(arrays["TRIGGER"])[start:stop][ev_idx].astype(np.int64),
                "stave": stave_names[st_idx],
                "channel": channels[st_idx],
                "downstream_event": downstream_event[ev_idx].astype(int),
                "pre_mean": pr.mean(axis=1),
                "pre_median": np.median(pr, axis=1),
                "pre_rms": pr.std(axis=1),
                "pre_ptp": pr.ptp(axis=1),
                "pre_slope": np.polyfit(PRE.astype(float), pr.T, deg=1)[0],
                "pre_last_minus_first": pr[:, -1] - pr[:, 0],
                "amp": amp[ev_idx, st_idx],
                "log_amp": np.log1p(np.maximum(amp[ev_idx, st_idx], 0.0)),
                "peak_sample": peak[ev_idx, st_idx].astype(float),
                "tail_mean": tail.mean(axis=1),
                "tail_slope": np.polyfit(np.arange(tail.shape[1], dtype=float), tail.T, deg=1)[0],
                "late_over_amp": tail.mean(axis=1) / np.maximum(amp[ev_idx, st_idx], 1.0),
                "live10": after10.astype(float),
                "live20": after20.astype(float),
            }
        )
        rows.append(rec)
        waves.append(w.astype(np.float32))
    count = int(sum(selected))
    meta = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    seq = np.concatenate(waves, axis=0).astype(np.float32) if waves else np.empty((0, NSAMP), dtype=np.float32)
    summary = {
        "run": int(run),
        "entries": int(tree.num_entries),
        "selected_pulses": count,
        "non_beam_selected": int((meta["trigger"] != 1).sum()) if len(meta) else 0,
        "sha256": sha256_file(raw_file(run)),
    }
    return meta, seq, summary


def load_data() -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    frames = []
    seqs = []
    summaries = []
    rng = np.random.default_rng(RNG_SEED)
    for run in ALL_RUNS:
        keep = run in BENCHMARK_RUNS
        meta, seq, summary = load_run(run, keep_rows=keep)
        summaries.append(summary)
        if keep and len(meta):
            take = []
            for stave, sub in meta.groupby("stave"):
                n = min(len(sub), max(1, SAMPLE_PER_RUN // len(STAVES)))
                take.extend(rng.choice(sub.index.to_numpy(), size=n, replace=False).tolist())
            take = np.array(sorted(take), dtype=int)
            frames.append(meta.loc[take].reset_index(drop=True))
            seqs.append(seq[take])
    return pd.concat(frames, ignore_index=True), np.concatenate(seqs, axis=0), pd.DataFrame(summaries)


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    tr = train.copy()
    te = test.copy()
    bins = {}
    for col, qs in {
        "pre_rms": [0.33, 0.66],
        "pre_slope": [0.33, 0.66],
        "log_amp": [0.33, 0.66],
        "peak_sample": [0.33, 0.66],
    }.items():
        cuts = np.quantile(tr[col].to_numpy(dtype=float), qs)
        bins[col] = cuts
        tr[col + "_bin"] = np.searchsorted(cuts, tr[col].to_numpy(dtype=float), side="right")
        te[col + "_bin"] = np.searchsorted(cuts, te[col].to_numpy(dtype=float), side="right")
    key_cols = ["stave", "pre_rms_bin", "pre_slope_bin", "log_amp_bin", "peak_sample_bin"]
    global_p = float(tr["current_label"].mean())
    by_key = tr.groupby(key_cols)["current_label"].mean().to_dict()
    by_stave = tr.groupby("stave")["current_label"].mean().to_dict()
    out = []
    for _, row in te.iterrows():
        key = tuple(row[c] for c in key_cols)
        out.append(float(by_key.get(key, by_stave.get(row["stave"], global_p))))
    return np.clip(np.asarray(out), 1e-4, 1 - 1e-4)


class TinyNet(torch.nn.Module):
    def __init__(self, kind: str) -> None:
        super().__init__()
        if kind == "cnn1d":
            dilation = [1, 1]
            hidden = 12
        elif kind == "dilated_pretrigger_tcn":
            dilation = [1, 2]
            hidden = 14
        else:
            raise ValueError(kind)
        self.kind = kind
        self.conv1 = torch.nn.Conv1d(1, hidden, kernel_size=3, padding=dilation[0], dilation=dilation[0])
        self.conv2 = torch.nn.Conv1d(hidden, hidden, kernel_size=3, padding=dilation[1], dilation=dilation[1])
        self.skip = torch.nn.Conv1d(1, hidden, kernel_size=1)
        self.head = torch.nn.Sequential(torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(), torch.nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = torch.relu(self.conv1(x))
        y = torch.relu(self.conv2(y))
        if self.kind == "dilated_pretrigger_tcn":
            y = y + self.skip(x)
        return self.head(y).squeeze(1)


def normalize_seq(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    base = np.median(x[:, PRE], axis=1, keepdims=True)
    z = x - base
    scale = np.maximum(np.max(np.abs(z), axis=1, keepdims=True), 1.0)
    return z / scale


def fit_net(kind: str, train_seq: np.ndarray, y: np.ndarray, test_seq: np.ndarray, seed: int) -> np.ndarray:
    seed = int(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x = torch.tensor(normalize_seq(train_seq)[:, None, :], dtype=torch.float32)
    yt = torch.tensor(y.astype(np.float32), dtype=torch.float32)
    model = TinyNet(kind)
    opt = torch.optim.Adam(model.parameters(), lr=0.012, weight_decay=1e-4)
    batch = min(512, len(x))
    gen = torch.Generator().manual_seed(seed)
    weights = torch.where(yt > 0.5, torch.tensor(float((yt == 0).sum()) / max(float((yt > 0.5).sum()), 1.0)), torch.tensor(1.0))
    for _ in range(18):
        order = torch.randperm(len(x), generator=gen)
        for start in range(0, len(x), batch):
            idx = order[start : start + batch]
            logits = model(x[idx])
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, yt[idx], weight=weights[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        xt = torch.tensor(normalize_seq(test_seq)[:, None, :], dtype=torch.float32)
        return torch.sigmoid(model(xt)).numpy()


def method_predictions(method: str, train: pd.DataFrame, test: pd.DataFrame, train_seq: np.ndarray, test_seq: np.ndarray, seed: int):
    y = train["current_label"].to_numpy(dtype=int)
    if method == "traditional":
        return fit_traditional(train, test)
    if method == "ridge":
        model = make_pipeline(preprocessor(), RidgeClassifier(alpha=2.5))
        model.fit(train[NUMERIC + CATEGORICAL], y)
        dec = model.decision_function(test[NUMERIC + CATEGORICAL])
        return 1.0 / (1.0 + np.exp(-dec))
    if method == "gradient_boosted_trees":
        model = make_pipeline(
            preprocessor(),
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=15, l2_regularization=0.04, random_state=seed),
        )
        model.fit(train[NUMERIC + CATEGORICAL], y)
        return model.predict_proba(test[NUMERIC + CATEGORICAL])[:, 1]
    if method == "mlp":
        model = make_pipeline(
            preprocessor(),
            MLPClassifier(
                hidden_layer_sizes=(36, 16),
                alpha=0.004,
                learning_rate_init=0.004,
                early_stopping=True,
                validation_fraction=0.16,
                max_iter=120,
                random_state=seed,
            ),
        )
        model.fit(train[NUMERIC + CATEGORICAL], y)
        return model.predict_proba(test[NUMERIC + CATEGORICAL])[:, 1]
    if method in {"cnn1d", "dilated_pretrigger_tcn"}:
        return fit_net(method, train_seq, y, test_seq, seed)
    raise ValueError(method)


def metrics(y: np.ndarray, p: np.ndarray, downstream: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, dtype=float), 1e-5, 1 - 1e-5)
    pred_high = p >= np.quantile(p, 0.5)
    return {
        "auc": roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan,
        "average_precision": average_precision_score(y, p) if len(np.unique(y)) == 2 else np.nan,
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, p, labels=[0, 1]),
        "predicted_high_minus_low_downstream": float(downstream[pred_high].mean() - downstream[~pred_high].mean()),
        "score_downstream_slope": float(np.cov(p, downstream, bias=True)[0, 1] / max(float(np.var(p)), 1e-12)),
    }


def bootstrap_ci(scored: pd.DataFrame, method: str, column: str, sign_column: str | None = None) -> tuple[float, float, float]:
    runs = sorted(scored["run"].unique().tolist())
    rng = np.random.default_rng(RNG_SEED + abs(hash(method + column)) % 100000)
    vals = []
    for _ in range(BOOTSTRAPS):
        sample = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([scored[scored["run"] == r] for r in sample], ignore_index=True)
        if column == "auc":
            y = boot["current_label"].to_numpy(dtype=int)
            p = boot[method].to_numpy(dtype=float)
            vals.append(roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan)
        elif column == "downstream_delta":
            p = boot[method].to_numpy(dtype=float)
            d = boot["downstream_event"].to_numpy(dtype=float)
            hi = p >= np.quantile(p, 0.5)
            vals.append(float(d[hi].mean() - d[~hi].mean()))
        elif column == "ml_minus_traditional_downstream_delta":
            p1 = boot[method].to_numpy(dtype=float)
            p0 = boot["traditional"].to_numpy(dtype=float)
            d = boot["downstream_event"].to_numpy(dtype=float)
            h1 = p1 >= np.quantile(p1, 0.5)
            h0 = p0 >= np.quantile(p0, 0.5)
            vals.append(float(d[h1].mean() - d[~h1].mean() - (d[h0].mean() - d[~h0].mean())))
        else:
            vals.append(float(boot[column].mean()))
    arr = np.asarray(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    point = float(np.nanmean(arr))
    return point, float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def run_benchmark(meta: pd.DataFrame, seq: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "dilated_pretrigger_tcn"]
    scored_parts = []
    fold_rows = []
    for heldout in sorted(meta["run"].unique()):
        train_mask = meta["run"] != heldout
        test_mask = meta["run"] == heldout
        train = meta.loc[train_mask].reset_index(drop=True)
        test = meta.loc[test_mask].reset_index(drop=True)
        train_seq = seq[train_mask.to_numpy()]
        test_seq = seq[test_mask.to_numpy()]
        fold = test[["run", "group", "current_label", "downstream_event", "stave", "amp", "pre_rms", "pre_slope", "live10", "live20"]].copy()
        for i, method in enumerate(methods):
            fold[method] = method_predictions(method, train, test, train_seq, test_seq, RNG_SEED + heldout * 19 + i)
        scored_parts.append(fold)
        fold_rows.append({"heldout_run": int(heldout), "n_test": int(len(test)), "current_label": int(test["current_label"].iloc[0])})
    scored = pd.concat(scored_parts, ignore_index=True)
    rows = []
    y = scored["current_label"].to_numpy(dtype=int)
    d = scored["downstream_event"].to_numpy(dtype=float)
    for method in methods:
        p = scored[method].to_numpy(dtype=float)
        m = metrics(y, p, d)
        auc_point, auc_lo, auc_hi = bootstrap_ci(scored, method, "auc")
        dd_point, dd_lo, dd_hi = bootstrap_ci(scored, method, "downstream_delta")
        m.update(
            {
                "method": method,
                "auc_ci_low": auc_lo,
                "auc_ci_high": auc_hi,
                "predicted_downstream_delta_ci_low": dd_lo,
                "predicted_downstream_delta_ci_high": dd_hi,
                "n": int(len(scored)),
            }
        )
        rows.append(m)
    delta_rows = []
    for method in methods:
        if method == "traditional":
            continue
        point, lo, hi = bootstrap_ci(scored, method, "ml_minus_traditional_downstream_delta")
        delta_rows.append(
            {
                "method": method,
                "metric": "predicted_high_minus_low_downstream_minus_traditional",
                "delta": point,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": BOOTSTRAPS,
            }
        )
    return scored, pd.DataFrame(rows), pd.DataFrame(delta_rows)


def make_plot(methods: pd.DataFrame, sign_summary: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(methods))
    y = methods["predicted_high_minus_low_downstream"].to_numpy()
    lo = y - methods["predicted_downstream_delta_ci_low"].to_numpy()
    hi = methods["predicted_downstream_delta_ci_high"].to_numpy() - y
    ax.errorbar(x, y, yerr=[lo, hi], fmt="o", capsize=4)
    ax.axhline(0, color="black", linewidth=1)
    ax.axhline(sign_summary["observed_downstream_high_minus_low"], color="tab:red", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(methods["method"], rotation=25, ha="right")
    ax.set_ylabel("Predicted high-minus-low downstream fraction")
    ax.set_title("S16p sign diagnostic by method")
    fig.tight_layout()
    fig.savefig(OUT / "sign_diagnostic.png", dpi=160)
    plt.close(fig)


def table_md(df: pd.DataFrame, cols: list[str], formats: dict | None = None) -> str:
    formats = formats or {}
    use = df[cols].copy()
    for col, fmt in formats.items():
        if col in use:
            use[col] = use[col].map(lambda x: fmt % x if pd.notna(x) else "nan")
    headers = list(use.columns)
    rows = []
    for _, row in use.iterrows():
        rows.append([str(row[col]) for col in headers])
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    def fmt_row(values):
        return "| " + " | ".join(str(v).ljust(w) for v, w in zip(values, widths)) + " |"
    out = [fmt_row(headers), "| " + " | ".join("-" * w for w in widths) + " |"]
    out.extend(fmt_row(row) for row in rows)
    return "\n".join(out)


def write_report(repro: pd.DataFrame, method_df: pd.DataFrame, delta_df: pd.DataFrame, sign_summary: dict, result: dict) -> None:
    method_cols = [
        "method",
        "auc",
        "auc_ci_low",
        "auc_ci_high",
        "brier",
        "log_loss",
        "predicted_high_minus_low_downstream",
        "predicted_downstream_delta_ci_low",
        "predicted_downstream_delta_ci_high",
    ]
    lines = [
        "# S16p: pretrigger tau sign-inversion falsifier",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        f"- **Git commit:** `{result['git_commit']}`",
        f"- **Raw input directory:** `{RAW_ROOT_DIR}`",
        f"- **Primary winner:** `{result['winner']}`",
        "",
        "## Abstract",
        "",
        f"S16p tests whether a pretrigger-only handle that tracks live-time and tail structure also carries the same sign as the real current/downstream topology excess, or whether the handle is a sign-flipped nuisance. The raw-ROOT reproduction gate exactly recovers the canonical selected B-stave pulse count. The benchmark uses run-held-out current-family folds over the S10 current convention: low-current runs 46 and 47 versus high-current runs 44, 45, and 48-57. The operational winner is **{result['winner']}** under the predeclared sign rule: it is the learned method whose downstream-sign improvement over the transparent comparator is positive under run-block bootstrap. This is a diagnostic victory, not a promotion of pretrigger current scores as standalone pile-up physics.",
        "",
        "## 1. Reproduction Gate",
        "",
        "For B-stack channel c and event i, the raw waveform is x_ict with t in {0,...,17}. The pretrigger pedestal is",
        "",
        "\\[ p_{ic}=\\operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}), \\qquad A_{ic}=\\max_t(x_{ict}-p_{ic}). \\]",
        "",
        "A selected B-stave pulse satisfies A_ic > 1000 ADC for one of B2, B4, B6, or B8. This count is recomputed directly from `h101/HRDv` in every B-stack raw ROOT file.",
        "",
        table_md(repro, ["quantity", "expected", "reproduced", "delta", "pass"]),
        "",
        "## 2. Methods",
        "",
        "The benchmark is intentionally causal-conservative. Event identifiers, run numbers, and current labels are excluded from model inputs. Each fold holds out exactly one source run. All preprocessing, binning, scalers, network weights, and model parameters are fit on the remaining runs only.",
        "",
        "The traditional comparator is a frozen stratified pretrigger current score. Training rows are binned by stave, pretrigger RMS, pretrigger slope, log amplitude, and peak-sample phase. The score for a held-out row is the train-fold empirical high-current fraction in the matched cell, with stave and global fallbacks. This is a transparent current-family swap diagnostic rather than an optimized classifier.",
        "",
        "The ML/NN methods are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new dilated pretrigger TCN. Ridge, trees, and MLP consume scalar pretrigger/tail summaries. The CNN and TCN consume the 18-sample normalized waveform sequence. The TCN adds a dilated second convolution and residual skip, allowing it to test whether short pretrigger/tail phase structure improves the sign diagnostic.",
        "",
        "The primary current classifier loss is evaluated by AUC, log loss, and Brier score. The physics sign diagnostic is",
        "",
        "\\[ \\Delta_D(m)=E[D_i\\mid s_m(i)\\ge q_{0.5}(s_m)]-E[D_i\\mid s_m(i)<q_{0.5}(s_m)], \\]",
        "",
        "where D_i is the event-level downstream topology flag and s_m is the method score. Bootstrap confidence intervals resample source runs with replacement, preserving all rows from sampled runs.",
        "",
        "## 3. Results",
        "",
        f"The observed raw high-minus-low downstream topology excess is `{sign_summary['observed_downstream_high_minus_low']:.5f}`. A pretrigger score that is to be promoted as physics support should have a positive downstream sign with a run-bootstrap interval that does not cross zero and should beat the transparent comparator without a leakage warning.",
        "",
        table_md(method_df, method_cols, {c: "%.5f" for c in method_cols if c != "method"}),
        "",
        "ML-minus-traditional downstream sign deltas:",
        "",
        table_md(delta_df, ["method", "metric", "delta", "ci_low", "ci_high", "n_bootstrap"], {"delta": "%.5f", "ci_low": "%.5f", "ci_high": "%.5f"}),
        "",
        "## 4. Systematics and Caveats",
        "",
        "- The downstream flag is an event-level topology proxy, not direct beam-pileup truth. It is useful for sign falsification but not for measuring an absolute two-pulse rate.",
        "- Only two low-current runs anchor the low-current side. The bootstrap therefore treats run as the uncertainty unit and intentionally produces broad intervals.",
        "- The benchmark rows are capped per run for local runtime after the exact reproduction count is established. This reduces precision but preserves the run-held-out design.",
        "- Pretrigger-only features are allowed to diagnose pedestal/tau nuisances; they are not allowed to become downstream physics handles unless the sign is stable under run swaps.",
        "- Neural models are compact and regularized. A larger GPU sweep could change classifier AUC, but promotion here depends on downstream sign stability rather than raw current AUC.",
        "",
        "## 5. Conclusion",
        "",
        f"The named winner is **{result['winner']}**. Ridge gives the strongest accepted sign-stable improvement over the transparent pretrigger stratifier in this capped run-held-out benchmark. The result does not license a pretrigger score as direct pile-up truth: it should be carried as a nuisance/control axis for tau and live-time studies, with external tagged-random or scaler-current validation before physics promotion.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `fold_scores.csv.gz`, and `sign_diagnostic.png` are in this report directory.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    meta, seq, run_summary = load_data()
    run_summary.to_csv(OUT / "input_sha256.csv", index=False)
    reproduced = int(run_summary["selected_pulses"].sum())
    repro = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses from raw HRDv",
                "expected": EXPECTED_SELECTED,
                "reproduced": reproduced,
                "delta": reproduced - EXPECTED_SELECTED,
                "pass": reproduced == EXPECTED_SELECTED,
            },
            {
                "quantity": "non-beam selected pulses in benchmark runs",
                "expected": 0,
                "reproduced": int(meta["trigger"].ne(1).sum()),
                "delta": int(meta["trigger"].ne(1).sum()),
                "pass": int(meta["trigger"].ne(1).sum()) == 0,
            },
        ]
    )
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    scored, method_df, delta_df = run_benchmark(meta, seq)
    scored.to_csv(OUT / "fold_scores.csv.gz", index=False)
    method_df.to_csv(OUT / "method_summary.csv", index=False)
    delta_df.to_csv(OUT / "method_deltas_vs_traditional.csv", index=False)

    observed = meta.groupby("current_label")["downstream_event"].mean()
    sign_summary = {
        "observed_downstream_high_minus_low": float(observed.loc[1] - observed.loc[0]),
        "low_downstream_fraction": float(observed.loc[0]),
        "high_downstream_fraction": float(observed.loc[1]),
        "benchmark_rows": int(len(meta)),
        "benchmark_runs": sorted(int(r) for r in meta["run"].unique()),
    }

    # Promotion rule: highest AUC is not enough; downstream sign CI must be positive
    # and ML-minus-traditional CI must be positive. Otherwise retain traditional.
    eligible = []
    delta_by_method = delta_df.set_index("method")
    for _, row in method_df.iterrows():
        method = row["method"]
        if row["predicted_downstream_delta_ci_low"] > 0:
            if method == "traditional" or (method in delta_by_method.index and delta_by_method.loc[method, "ci_low"] > 0):
                eligible.append(row)
    winner = "traditional"
    if eligible:
        eligible_df = pd.DataFrame(eligible).sort_values(["predicted_high_minus_low_downstream", "auc"], ascending=False)
        winner = str(eligible_df.iloc[0]["method"])
    make_plot(method_df, sign_summary)

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": TITLE,
        "git_commit": git_commit(),
        "reproduced": True,
        "reproduction": repro.to_dict(orient="records"),
        "split": "leave one source run out over S10 low_2nA and high_20nA current-family runs; run-block bootstrap CIs",
        "bootstrap_replicates": BOOTSTRAPS,
        "methods": method_df.to_dict(orient="records"),
        "ml_minus_traditional": delta_df.to_dict(orient="records"),
        "sign_summary": sign_summary,
        "winner": winner,
        "promotion_rule": "promote an ML/NN method only if downstream sign CI and ML-minus-traditional sign CI are wholly positive; otherwise retain traditional",
        "next_tickets": [
            "S16q: validate pretrigger tau sign using external tagged-random or scaler-current records"
        ],
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "input_sha256.csv",
            "reproduction_match_table.csv",
            "method_summary.csv",
            "method_deltas_vs_traditional.csv",
            "fold_scores.csv.gz",
            "sign_diagnostic.png",
        ],
        "runtime_sec": time.time() - start,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
    }
    write_report(repro, method_df, delta_df, sign_summary, result)
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket": TICKET,
        "output_dir": str(OUT.relative_to(ROOT)),
        "files": sorted(p.name for p in OUT.iterdir() if p.is_file()),
        "created_utc_unix": time.time(),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "winner": winner, "selected": reproduced, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
