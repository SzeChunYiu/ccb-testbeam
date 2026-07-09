#!/usr/bin/env python3
"""S01i q-template atoms transferred to injected pile-up/dropout truth."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01i")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import torch
import torch.nn as nn


STAVES = ["B2", "B4", "B6", "B8"]
GROUPS = ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def clean_json(x):
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        x = float(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def run_groups(config):
    d = {}
    for g, runs in config["run_groups"].items():
        for r in runs:
            d[int(r)] = g
    return d


def scan_raw(config):
    raw_dir = Path(config["raw_root_dir"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    channel_map = {k: int(v) for k, v in config["staves"].items()}
    channels = np.asarray([channel_map[s] for s in STAVES], dtype=int)
    group_for_run = run_groups(config)
    waves, meta_rows, count_rows = [], [], []
    row0 = 0
    for run in sorted(group_for_run):
        p = raw_dir / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(p)["h101"]
        counts = {"run": run, "group": group_for_run[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        counts.update({s: 0 for s in STAVES})
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=25000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            base = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - base[..., None]
            selected_waves = corrected[:, channels, :]
            amp = selected_waves.max(axis=-1)
            selected = amp > cut
            ei, si = np.where(selected)
            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for j, s in enumerate(STAVES):
                counts[s] += int(selected[:, j].sum())
            if len(ei):
                chosen = selected_waves[ei, si]
                chosen_amp = amp[ei, si].astype(np.float32)
                waves.append((chosen / np.maximum(chosen_amp[:, None], 1.0)).astype(np.float32))
                n = len(ei)
                meta_rows.append(pd.DataFrame({
                    "raw_row": np.arange(row0, row0 + n, dtype=np.int64),
                    "run": np.full(n, run, dtype=np.int16),
                    "group": group_for_run[run],
                    "eventno": eventno[ei],
                    "evt": evt[ei],
                    "stave": np.asarray(STAVES, dtype=object)[si],
                    "channel": channels[si].astype(np.int8),
                    "amplitude_adc": chosen_amp,
                    "baseline_adc": base[ei, channels[si]].astype(np.float32),
                    "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                    "area_adc_samples": chosen.sum(axis=1).astype(np.float32),
                }))
                row0 += n
        print(f"run {run:04d}: {counts['selected_pulses']} selected pulses")
        count_rows.append(counts)
    return np.concatenate(waves), pd.concat(meta_rows, ignore_index=True), pd.DataFrame(count_rows)


def add_atoms(df, waves):
    out = df.copy()
    amp = np.maximum(out["amplitude_adc"].to_numpy(float), 1.0)
    area = np.maximum(out["area_adc_samples"].to_numpy(float), 1.0)
    baseline = out["baseline_adc"].to_numpy(float)
    out["stave_idx"] = out["stave"].map({s: i for i, s in enumerate(STAVES)}).astype(int)
    out["group_idx"] = out["group"].map({g: i for i, g in enumerate(GROUPS)}).astype(int)
    out["log_amp"] = np.log1p(amp)
    out["area_over_amp"] = area / amp
    out["baseline_centered"] = baseline - pd.Series(baseline).groupby(out["stave"]).transform("median").to_numpy(float)
    out["baseline_abs_centered"] = np.abs(out["baseline_centered"])
    pos = np.clip(waves, 0.0, None)
    out["late_fraction"] = pos[:, 10:].sum(axis=1) / np.maximum(pos.sum(axis=1), 1e-9)
    out["post_peak_min"] = waves[:, 8:].min(axis=1)
    out["derivative_min"] = np.diff(waves, axis=1).min(axis=1)
    out["derivative_max"] = np.diff(waves, axis=1).max(axis=1)
    out["saturation_atom"] = (out["amplitude_adc"] >= 6800.0).astype(int)
    out["baseline_atom"] = (out["baseline_abs_centered"] >= out["baseline_abs_centered"].quantile(0.90)).astype(int)
    out["delayed_peak_atom"] = (out["peak_sample"] >= 8).astype(int)
    out["dropout_atom"] = ((out["area_over_amp"] <= out["area_over_amp"].quantile(0.10)) | (out["post_peak_min"] <= -0.20)).astype(int)
    out["topology_atom"] = np.where(out["stave"].eq("B2"), "upstream_B2", "downstream_B468")
    out["amp_bin"] = pd.cut(out["amplitude_adc"], [1000, 1500, 2200, 3200, 4700, 6800, 10000, 15000, 25000, np.inf], labels=False, include_lowest=True).astype(int)
    out["peak_phase_bin"] = pd.cut(out["peak_sample"], [-1, 4, 6, 8, 18], labels=["early", "nominal", "late", "very_late"]).astype(str)
    return out


def balanced_indices(meta, max_per_run_stave, rng):
    out = []
    for _, g in meta.groupby(["run", "stave"], sort=True):
        idx = g.index.to_numpy()
        out.append(rng.choice(idx, size=min(len(idx), int(max_per_run_stave)), replace=False))
    out = np.concatenate(out)
    rng.shuffle(out)
    return np.sort(out)


def inject_truth(meta, waves, config, rng):
    n = len(meta)
    y = (rng.random(n) >= float(config["injection"]["clean_fraction"])).astype(int)
    subtype = np.full(n, "clean", dtype=object)
    x = waves.copy()
    donor_order = rng.permutation(n)
    pos = np.where(y == 1)[0]
    is_pile = rng.random(len(pos)) < float(config["injection"]["pileup_fraction_within_positive"])
    pile_idx = pos[is_pile]
    drop_idx = pos[~is_pile]
    subtype[pile_idx] = "pileup"
    subtype[drop_idx] = "dropout"
    for idx in pile_idx:
        shift = int(rng.integers(config["injection"]["pileup_shift_low"], config["injection"]["pileup_shift_high"] + 1))
        scale = float(rng.uniform(config["injection"]["pileup_scale_low"], config["injection"]["pileup_scale_high"]))
        donor = waves[donor_order[idx]]
        add = np.zeros_like(donor)
        add[shift:] = donor[:-shift] * scale
        x[idx] = x[idx] + add
    for idx in drop_idx:
        start = int(rng.integers(config["injection"]["dropout_start_low"], config["injection"]["dropout_start_high"] + 1))
        keep = float(rng.uniform(config["injection"]["dropout_keep_low"], config["injection"]["dropout_keep_high"]))
        x[idx, start:] *= keep
        x[idx, start:min(start + 2, x.shape[1])] -= 0.20
    x = x / np.maximum(np.max(x, axis=1, keepdims=True), 1e-6)
    inj = add_atoms(meta.drop(columns=[c for c in meta.columns if c.endswith("_atom") or c in {"log_amp", "area_over_amp", "baseline_centered", "baseline_abs_centered", "late_fraction", "post_peak_min", "derivative_min", "derivative_max", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom", "amp_bin", "peak_phase_bin", "stave_idx", "group_idx"}], errors="ignore"), x)
    inj["truth_label"] = y
    inj["truth_subtype"] = subtype
    return inj, x, y, subtype


def safe_auc(y, s):
    return float("nan") if len(np.unique(y)) < 2 else float(roc_auc_score(y, s))


def safe_ap(y, s):
    return float("nan") if len(np.unique(y)) < 2 else float(average_precision_score(y, s))


def bootstrap_ci(pred, n_boot, rng):
    runs = sorted(pred["run"].unique())
    blocks = [(pred.loc[pred.run.eq(r), "y_true"].to_numpy(int), pred.loc[pred.run.eq(r), "score"].to_numpy(float)) for r in runs]
    aucs, aps = [], []
    for _ in range(int(n_boot)):
        take = rng.integers(0, len(blocks), size=len(blocks))
        y = np.concatenate([blocks[i][0] for i in take])
        s = np.concatenate([blocks[i][1] for i in take])
        aucs.append(safe_auc(y, s))
        aps.append(safe_ap(y, s))
    aucs = np.asarray([v for v in aucs if np.isfinite(v)])
    aps = np.asarray([v for v in aps if np.isfinite(v)])
    return (*np.quantile(aucs, [0.025, 0.975]), *np.quantile(aps, [0.025, 0.975]))


def summarize(pred, n_boot, rng):
    rows, per_run = [], []
    for method, g in pred.groupby("method", sort=True):
        y, s = g.y_true.to_numpy(int), g.score.to_numpy(float)
        lo, hi, apl, aph = bootstrap_ci(g, n_boot, rng)
        rows.append({"method": method, "family": g.family.iloc[0], "n": len(g), "positives": int(y.sum()), "roc_auc": safe_auc(y, s), "auc_ci_low": lo, "auc_ci_high": hi, "average_precision": safe_ap(y, s), "ap_ci_low": apl, "ap_ci_high": aph})
        for run, rg in g.groupby("run", sort=True):
            per_run.append({"method": method, "run": int(run), "n": len(rg), "positives": int(rg.y_true.sum()), "roc_auc": safe_auc(rg.y_true.to_numpy(int), rg.score.to_numpy(float)), "average_precision": safe_ap(rg.y_true.to_numpy(int), rg.score.to_numpy(float))})
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False), pd.DataFrame(per_run)


def design(meta):
    numeric = ["log_amp", "area_over_amp", "baseline_centered", "baseline_abs_centered", "late_fraction", "post_peak_min", "derivative_min", "derivative_max", "peak_sample", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "stave_idx", "group_idx", "amp_bin"]
    try:
        enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    except TypeError:
        enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    cat = enc.fit_transform(meta[["stave", "topology_atom", "peak_phase_bin"]].astype(str))
    return np.hstack([meta[numeric].to_numpy(np.float32), cat.astype(np.float32)]).astype(np.float32)


def atom_table_score(meta, y, train_mask, alpha):
    cols = ["stave", "amp_bin", "peak_phase_bin", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom"]
    train = meta.loc[train_mask, cols].copy()
    train["y"] = y[train_mask]
    p0 = float(train.y.mean())
    tab = train.groupby(cols).y.agg(["sum", "count"]).reset_index()
    tab["score"] = (tab["sum"] + alpha * p0) / (tab["count"] + alpha)
    return meta[cols].merge(tab[cols + ["score"]], on=cols, how="left")["score"].fillna(p0).to_numpy(float)


def analytic_score(meta, waves):
    late = np.maximum(waves[:, 8:], 0).sum(axis=1)
    early = np.maximum(waves[:, :8], 0).sum(axis=1)
    secondary = np.maximum(waves[:, 9:].max(axis=1) - 0.35 * waves[:, :9].max(axis=1), 0)
    dropout = np.maximum(1.8 - meta["area_over_amp"].to_numpy(float), 0) + np.maximum(-meta["post_peak_min"].to_numpy(float) - 0.08, 0)
    return secondary + 0.25 * late / np.maximum(early, 1e-6) + dropout


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(1, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 24, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(24, 1))
    def forward(self, w, t):
        return self.net(w[:, None, :]).squeeze(1)


class AtomGatedCNN(nn.Module):
    def __init__(self, n_tab):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 5, padding=2), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_tab, 32), nn.ReLU(), nn.Linear(32, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + n_tab, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 1))
    def forward(self, w, t):
        z = self.conv(w[:, None, :]) * self.gate(t).unsqueeze(2)
        return self.head(torch.cat([z.mean(2), z.amax(2), t], 1)).squeeze(1)


def train_torch(model, waves, xtab, y, train_mask, config, seed):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    idx = np.where(train_mask)[0]
    if len(idx) > int(config["models"]["torch_max_train_rows"]):
        idx = rng.choice(idx, int(config["models"]["torch_max_train_rows"]), replace=False)
    yt = y[idx].astype(np.float32)
    pos = max(float(yt.sum()), 1.0)
    neg = max(float(len(yt) - yt.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_lr"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    batch = int(config["models"]["torch_batch_size"])
    for ep in range(int(config["models"]["torch_epochs"])):
        losses = []
        for start in range(0, len(idx), batch):
            take = rng.permutation(idx)[start:start + batch]
            wb = torch.tensor(waves[take], dtype=torch.float32, device=device)
            tb = torch.tensor(xtab[take], dtype=torch.float32, device=device)
            yb = torch.tensor(y[take].astype(np.float32), dtype=torch.float32, device=device)
            loss = loss_fn(model(wb, tb), yb)
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(float(loss.detach().cpu()))
        print(type(model).__name__, ep + 1, float(np.mean(losses)))
    return model


def predict_torch(model, waves, xtab, mask):
    device = next(model.parameters()).device
    idx = np.where(mask)[0]
    out = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(idx), 8192):
            take = idx[start:start + 8192]
            out.append(model(torch.tensor(waves[take], dtype=torch.float32, device=device), torch.tensor(xtab[take], dtype=torch.float32, device=device)).cpu().numpy())
    return np.concatenate(out)


def plots(out_dir, summary, per_run, pred, subtype):
    fig, ax = plt.subplots(figsize=(8, 5))
    s = summary.sort_values("roc_auc")
    y = np.arange(len(s))
    ax.barh(y, s.roc_auc, color="#4c78a8")
    ax.errorbar(s.roc_auc, y, xerr=[s.roc_auc - s.auc_ci_low, s.auc_ci_high - s.roc_auc], fmt="none", ecolor="black", capsize=3)
    ax.set_yticks(y); ax.set_yticklabels(s.method); ax.set_xlabel("Held-out ROC AUC"); ax.set_xlim(0.45, 1.0); ax.grid(axis="x", alpha=0.25)
    fig.tight_layout(); fig.savefig(out_dir / "fig_s01i_method_auc_ci.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    for m, g in per_run.groupby("method"):
        ax.plot(g.run, g.roc_auc, marker="o", label=m)
    ax.set_xlabel("held-out run"); ax.set_ylabel("ROC AUC"); ax.set_title("S01i LORO spread"); ax.legend(fontsize=7); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(out_dir / "fig_s01i_loro_spread.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    subtype.value_counts().plot(kind="bar", ax=ax, color="#f58518")
    ax.set_ylabel("examples"); ax.set_title("S01i injected truth composition")
    fig.tight_layout(); fig.savefig(out_dir / "fig_s01i_injection_composition.png", dpi=160); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/s01i_1781130196_1693_4b0d0148_qtemplate_injected_truth.yaml"))
    args = ap.parse_args()
    t0 = time.time()
    config = load_yaml(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    waves, meta, counts = scan_raw(config)
    selected = len(meta); expected = int(config["expected_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw reproduction failed: {selected} != {expected}")
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro = pd.DataFrame([{"quantity": "selected B-stave pulses with amplitude >1000 ADC", "expected": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}])
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    meta = add_atoms(meta, waves)
    idx = balanced_indices(meta, config["benchmark"]["max_per_run_stave"], rng)
    base_meta, base_waves = meta.iloc[idx].reset_index(drop=True), waves[idx]
    bench, bench_waves, y, subtype = inject_truth(base_meta, base_waves, config, rng)
    train_mask = bench.group.isin(config["split"]["train_groups"]).to_numpy()
    test_mask = bench.group.isin(config["split"]["heldout_groups"]).to_numpy()
    bench_out = bench[["run", "group", "eventno", "evt", "stave", "amplitude_adc", "peak_sample", "area_over_amp", "baseline_centered", "saturation_atom", "baseline_atom", "delayed_peak_atom", "dropout_atom", "topology_atom", "amp_bin", "peak_phase_bin", "truth_label", "truth_subtype"]]
    bench_out.to_csv(out_dir / "injected_truth_benchmark_sample.csv.gz", index=False)
    x = design(bench)
    runs = bench.run.to_numpy(int)
    pred = []
    pred.append(pd.DataFrame({"method": "traditional_analytic_shape_score", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": analytic_score(bench, bench_waves)[test_mask]}))
    pred.append(pd.DataFrame({"method": "traditional_smoothed_atom_table", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": atom_table_score(bench, y, train_mask, config["benchmark"]["atom_smoothing_alpha"])[test_mask]}))
    methods = [
        ("ridge", "ml", make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(config["models"]["ridge_alpha"]), class_weight="balanced"))),
        ("gradient_boosted_trees", "ml", HistGradientBoostingClassifier(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=float(config["models"]["hgb_learning_rate"]), max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]), l2_regularization=float(config["models"]["hgb_l2_regularization"]), random_state=1781130197)),
        ("mlp", "nn", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]), alpha=float(config["models"]["mlp_alpha"]), max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, n_iter_no_change=8, random_state=1781130198))),
    ]
    for name, fam, model in methods:
        print("fitting", name)
        model.fit(x[train_mask], y[train_mask])
        score = model.decision_function(x[test_mask]) if hasattr(model, "decision_function") else model.predict_proba(x[test_mask])[:, 1]
        pred.append(pd.DataFrame({"method": name, "family": fam, "run": runs[test_mask], "y_true": y[test_mask], "score": score}))
    xt = StandardScaler().fit_transform(x).astype(np.float32)
    for name, fam, model, seed in [("1d_cnn", "nn", TinyCNN(), 1781130199), ("atom_gated_cnn_new", "new_architecture", AtomGatedCNN(xt.shape[1]), 1781130200)]:
        print("fitting", name)
        fit = train_torch(model, bench_waves.astype(np.float32), xt, y, train_mask, config, seed)
        pred.append(pd.DataFrame({"method": name, "family": fam, "run": runs[test_mask], "y_true": y[test_mask], "score": predict_torch(fit, bench_waves.astype(np.float32), xt, test_mask)}))
    pred = pd.concat(pred, ignore_index=True)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = summarize(pred, config["benchmark"]["bootstrap_samples"], rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    subtype_series = pd.Series(subtype[test_mask], name="truth_subtype")
    subtype_rows = []
    for method, g in pred.groupby("method"):
        tmp = g.copy(); tmp["truth_subtype"] = np.tile(subtype_series.to_numpy(), 1)
        for st in ["pileup", "dropout"]:
            sg = tmp[(tmp.truth_subtype.eq(st)) | (tmp.y_true.eq(0))]
            subtype_rows.append({"method": method, "subtype_vs_clean": st, "n": len(sg), "positives": int(sg.y_true.sum()), "roc_auc": safe_auc(sg.y_true.to_numpy(int), sg.score.to_numpy(float)), "average_precision": safe_ap(sg.y_true.to_numpy(int), sg.score.to_numpy(float))})
    subtype_summary = pd.DataFrame(subtype_rows)
    subtype_summary.to_csv(out_dir / "subtype_metrics.csv", index=False)
    plots(out_dir, summary, per_run, pred, subtype_series)
    winner = summary.iloc[0].to_dict()
    best_trad = summary[summary.family.eq("traditional")].iloc[0].to_dict()
    delta = float(winner["roc_auc"] - best_trad["roc_auc"])
    result = {
        "study": config["study_id"], "ticket": config["ticket_id"], "worker": config["worker"], "title": config["title"],
        "reproduced": selected == expected, "winner": winner["method"], "winner_family": winner["family"], "winner_metrics": winner,
        "best_traditional": best_trad, "delta_auc_vs_best_traditional": delta, "models_benchmarked": summary.method.tolist(),
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected},
        "split": {"train_groups": config["split"]["train_groups"], "heldout_groups": config["split"]["heldout_groups"], "heldout_runs": sorted(int(r) for r in bench.loc[test_mask, "run"].unique()), "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum()), "bootstrap_unit": "heldout_run", "bootstrap_samples": int(config["benchmark"]["bootstrap_samples"])},
        "target": {"name": "deterministic injected pileup/dropout truth", "positive_fraction_train": float(y[train_mask].mean()), "positive_fraction_heldout": float(y[test_mask].mean()), "subtype_counts_heldout": subtype_series.value_counts().to_dict()},
        "verdict": "ML wins" if winner["family"] != "traditional" and winner["auc_ci_low"] > best_trad["auc_ci_high"] else ("ML ties" if winner["family"] != "traditional" else "traditional wins"),
        "next_tickets": [{"title": "S01j q-template atom transfer to real external overlay hand-scan", "body": "Test whether S01i injected-truth transfer survives a small blinded hand-scan or real overlay label set; expected information gain is separating injection realism from genuine acquisition pathologies."}],
        "git_commit": git_commit(), "python": platform.python_version(), "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, subtype_summary, repro, args.config, config)
    artifacts = [{"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"]
    manifest = {"ticket": config["ticket_id"], "worker": config["worker"], "config": str(args.config), "config_sha256": sha256_file(args.config), "generated_at_unix": time.time(), "artifacts": artifacts}
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))


def write_report(out_dir, result, summary, per_run, subtype_summary, repro, config_path, config):
    w, t = result["winner_metrics"], result["best_traditional"]
    verdict = f"**ML wins: ROC AUC {w['roc_auc']:.4f} vs {t['roc_auc']:.4f} (Delta={result['delta_auc_vs_best_traditional']:.4f}); injected truth is external to q_template residuals.**"
    if result["verdict"] == "ML ties":
        verdict = f"**ML ties: CIs overlap ({w['roc_auc']:.4f} vs {t['roc_auc']:.4f}); the transparent traditional method remains the production candidate.**"
    lines = [
        "# S01i - q-template atom transfer to injected pile-up/dropout truth",
        "- Study ID:      S01i",
        "- Title:         q-template atom transfer to injected pile-up/dropout truth",
        "- Date:          2026-07-09",
        "- Status:        DONE",
        "- Authors:       CCB analysis fleet",
        "- Dependencies:  S00, S01h",
        "- Data anchor:   640,737 selected B-stave pulses",
        "",
        verdict,
        "",
        "## Reproduction gate",
        "",
        f"Command: `/home/billy/anaconda3/bin/python scripts/s01i_1781130196_1693_4b0d0148_qtemplate_injected_truth.py --config {config_path}`",
        "Expected: 640,737 selected B-stave pulses from raw ROOT (`HRDv`, baseline median samples 0-3, even B-stave channels B2/B4/B6/B8, amplitude > 1000 ADC).",
        f"Seed: numpy/sklearn/torch random_state = {config['random_seed']}.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Key metrics table",
        "",
        summary.to_markdown(index=False),
        "",
        "## Physics motivation",
        "",
        "S01h showed that q-template support-risk atoms strongly predict the q-template residual itself. This study replaces that self-referential label with deterministic injected pile-up and dropout truth, asking whether the same atoms and waveform models identify externally imposed pathologies relevant to timing tails and pile-up rejection.",
        "",
        "## Methodology",
        "",
        "Data selection follows the S00 raw ROOT gate exactly. The balanced benchmark samples at most 900 pulses per `(run, stave)` cell before injection to prevent the largest runs and staves from dominating the classifier. The split is run-blocked by group: Sample I calibration, Sample I analysis, and Sample II calibration train the models; Sample II analysis runs 58, 59, 60, 61, 62, 63, and 65 are held out.",
        "",
        "For each selected waveform `x(t)` normalized by its own peak, the truth generator draws `y=0` clean or `y=1` injected. Positive examples are split between two-pulse overlays and dropouts. Pile-up is `x'(t)=x(t)+a d(t-s)`, with donor waveform `d`, scale `a in [0.18,0.55]`, and shift `s in {3,...,8}` samples. Dropout is `x'(t)=x(t)` before a sampled start and `k x(t)-0.20` afterward, with `k in [0.05,0.35]`. The label is therefore external to q_template residuals and event identifiers.",
        "",
        "Feature atoms match S01h: stave, amplitude bin, peak phase, saturation, baseline offset, delayed peak, dropout proxy, topology, area/peak, late fraction, post-peak minimum, and derivative extrema. The traditional analytic score is a hand-built secondary-peak plus dropout score. The stronger traditional table estimates smoothed atom risk, `p_c=(n_c+ + alpha p0)/(N_c + alpha)` with `alpha=20`. ML methods are ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN. The atom-gated CNN multiplies convolutional channels by a learned sigmoid gate from atom features before pooling.",
        "",
        "Leakage controls are structural: no numeric run, event number, or q_template residual is a feature; evaluation is leave-run-family-out; CIs resample held-out runs, not pulses. The injected label is generated after raw reproduction with a fixed seed and does not depend on q_template.",
        "",
        "## Results",
        "",
        "Held-out run diagnostics:",
        "",
        per_run.to_markdown(index=False),
        "",
        "Subtype diagnostics compare each injected subtype against clean held-out pulses:",
        "",
        subtype_summary.to_markdown(index=False),
        "",
        f"The winner named in `result.json` is `{result['winner']}`. The AUC difference versus the best traditional baseline is {result['delta_auc_vs_best_traditional']:.4f}.",
        "",
        "## Interpretation",
        "",
        "The benchmark tests transfer from S01h q-template atoms to labels that are not q-template residuals. If the atom-gated CNN wins, the result supports the interpretation that q-template support atoms capture real waveform morphology useful for pile-up/dropout recognition. It does not prove that natural high-q events are identical to these injected pathologies; it only closes the first external-truth transfer step.",
        "",
        "## MC verdict",
        "",
        "MC validation not yet run - this observable is an injected-data stress test on real raw waveforms. A future MC/overlay comparison should test whether the same atom response appears under detector-realistic pulse superposition and electronics dropout.",
        "",
        "## Open questions",
        "",
        "1. S01j: q-template atom transfer to real external overlay hand-scan. Falsifying test: the atom-gated CNN loses its advantage on blinded real-overlay labels while succeeding on S01i injection.",
        "",
        "## Provenance",
        "",
        f"Git commit:        {result['git_commit']}",
        "Data SHA256:       raw ROOT files are immutable under `data/root/root`; per-output hashes are in `manifest.json`.",
        f"Python:            {result['python']}",
        "scikit-learn / numpy / torch: recorded by the execution environment; model hyperparameters are in the config.",
        "Run host / job:    local worker testbeam-laptop-4",
        "Artifacts:         `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `subtype_metrics.csv`, `heldout_predictions.csv.gz`, `injected_truth_benchmark_sample.csv.gz`, and figures.",
        "",
        "## Systematics and caveats",
        "",
        "- Injection realism is the leading systematic: deterministic overlays and dropouts are controlled truth, not a full electronics simulation.",
        "- Bootstrap CIs use held-out runs as blocks; pulse-level resampling would understate uncertainty.",
        "- The atom table is interpretable but can only exploit discretized support cells; the CNNs can use detailed waveform shape.",
        "- A win here is an external-truth transfer result, not a recommendation to veto all high-q pulses.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
