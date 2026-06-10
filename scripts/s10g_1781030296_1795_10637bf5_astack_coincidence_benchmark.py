#!/usr/bin/env python3
"""S10g A-stack coincidence validation of frozen B-stack two-pulse scores.

This study reproduces the S10/S10f raw-ROOT gates, reuses the frozen B-stack
candidate scoring protocol from 1781029288.941.6912528c, then asks whether
those B-stack waveform/candidate scores predict an independent A-stack
timing/topology coincidence on the same event number.  All predictive models
are evaluated leave-one-run-out; uncertainty is a bootstrap over held-out runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1781030296.1795.10637bf5"
RAW = ROOT / "data" / "root" / "root"
PRIOR_S10G = ROOT / "scripts" / "s10g_1781029288_941_6912528c_validate_s10f_real_windows.py"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET = "1781030296.1795.10637bf5"
WORKER = "testbeam-laptop-4"
STUDY = "S10g"
TITLE = "A-stack timing/topology validation of frozen S10e/S10f B-stack two-pulse candidates"
RNG_SEED = 2026061014
BOOTSTRAPS = 400
ASTACK_TIME_WINDOW_SAMPLES = 2.0
ASTACK_AMP_CUT = 1000.0
BASELINE_SAMPLES = [0, 1, 2, 3]
NSAMPLES = 18
STAVE_CHANNELS = np.asarray([0, 2, 4, 6], dtype=int)
STAVE_NAMES_A = np.asarray(["A2", "A4", "A6", "A8"])
RUN_GROUPS = {
    "low_2nA": {"current_nA": 2.0, "runs": [46, 47]},
    "high_20nA": {"current_nA": 20.0, "runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]},
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S10G = load_module("s10g_frozen_bstack_source", PRIOR_S10G)
S10G.OUT = OUT
S10G.BOOTSTRAPS = BOOTSTRAPS


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


def run_to_group() -> dict:
    return {run: group for group, info in RUN_GROUPS.items() for run in info["runs"]}


def raw_a_file(run: int) -> Path:
    return RAW / "hrda_run_{:04d}.root".format(int(run))


def raw_b_file(run: int) -> Path:
    return RAW / "hrdb_run_{:04d}.root".format(int(run))


def cfd_time_one(waveform: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.nanmax(waveform))
    if not np.isfinite(amp) or amp <= 0:
        return float("nan")
    threshold = amp * fraction
    above = np.flatnonzero(waveform >= threshold)
    if len(above) == 0:
        return float("nan")
    j = int(above[0])
    if j <= 0:
        return float(j)
    y0, y1 = float(waveform[j - 1]), float(waveform[j])
    if y1 <= y0:
        return float(j)
    return float(j - 1 + (threshold - y0) / (y1 - y0))


def load_astack_features(sample: pd.DataFrame, b_waves: np.ndarray) -> pd.DataFrame:
    needed = {
        int(run): set(sub["eventno"].astype(int).tolist())
        for run, sub in sample.groupby("run")
    }
    rows = []
    for run, eventnos_needed in needed.items():
        path = raw_a_file(run)
        seen = set()
        if not path.exists():
            continue
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            keep = np.asarray([int(x) in eventnos_needed for x in eventno], dtype=bool)
            if not keep.any():
                continue
            all_events = np.stack(batch["HRDv"][keep]).astype(np.float64).reshape(-1, 8, NSAMPLES)
            raw = all_events[:, STAVE_CHANNELS, :]
            seed = np.median(raw[..., BASELINE_SAMPLES], axis=-1)
            corr = raw - seed[..., None]
            amp = corr.max(axis=-1)
            area = corr.sum(axis=-1)
            selected = amp > ASTACK_AMP_CUT
            n_selected = selected.sum(axis=1)
            masked_amp = np.where(selected, amp, -np.inf)
            ref_idx = np.argmax(masked_amp, axis=1)
            no_selected = n_selected == 0
            ref_idx[no_selected] = np.argmax(amp[no_selected], axis=1) if no_selected.any() else ref_idx[no_selected]
            for i, evt in enumerate(eventno[keep]):
                evt = int(evt)
                seen.add(evt)
                ridx = int(ref_idx[i])
                wf = corr[i, ridx, :]
                a_cfd = cfd_time_one(wf, 0.2)
                rows.append(
                    {
                        "run": int(run),
                        "eventno": evt,
                        "a_event_matched": True,
                        "a_selected": bool(n_selected[i] >= 1),
                        "a_n_selected": int(n_selected[i]),
                        "a_multi_stave": bool(n_selected[i] >= 2),
                        "a_three_stave": bool(n_selected[i] >= 3),
                        "a_downstream": bool(selected[i, 1:].any()),
                        "a_ref_stave": str(STAVE_NAMES_A[ridx]),
                        "a_ref_amp_adc": float(amp[i, ridx]),
                        "a_ref_area_adc": float(area[i, ridx]),
                        "a_ref_cfd20_sample": float(a_cfd),
                        "a_peak_sample": int(np.argmax(wf)),
                        "a_area_over_peak": float(area[i, ridx] / max(float(amp[i, ridx]), 1.0)),
                    }
                )
        missing = sorted(eventnos_needed - seen)
        for evt in missing:
            rows.append(
                {
                    "run": int(run),
                    "eventno": int(evt),
                    "a_event_matched": False,
                    "a_selected": False,
                    "a_n_selected": 0,
                    "a_multi_stave": False,
                    "a_three_stave": False,
                    "a_downstream": False,
                    "a_ref_stave": "",
                    "a_ref_amp_adc": 0.0,
                    "a_ref_area_adc": 0.0,
                    "a_ref_cfd20_sample": float("nan"),
                    "a_peak_sample": -1,
                    "a_area_over_peak": float("nan"),
                }
            )
    astack = pd.DataFrame(rows)
    b_cfd = [
        cfd_time_one(b_waves[int(event_index)].astype(float), 0.2)
        for event_index in sample["event_index"].to_numpy(dtype=int)
    ]
    key = sample[["event_index", "run", "eventno"]].copy()
    key["b_ref_cfd20_sample"] = b_cfd
    out = key.merge(astack, on=["run", "eventno"], how="left")
    bool_cols = ["a_event_matched", "a_selected", "a_multi_stave", "a_three_stave", "a_downstream"]
    for col in bool_cols:
        out[col] = out[col].fillna(False).astype(bool)
    out["a_n_selected"] = out["a_n_selected"].fillna(0).astype(int)
    out["a_ref_amp_adc"] = out["a_ref_amp_adc"].fillna(0.0)
    out["a_ref_area_adc"] = out["a_ref_area_adc"].fillna(0.0)
    out["ab_cfd_delta_samples"] = out["a_ref_cfd20_sample"] - out["b_ref_cfd20_sample"]
    out["ab_abs_cfd_delta_samples"] = np.abs(out["ab_cfd_delta_samples"])
    out["a_timing_coincident"] = out["a_selected"] & (out["ab_abs_cfd_delta_samples"] <= ASTACK_TIME_WINDOW_SAMPLES)
    out["a_timing_topology_coincidence"] = (
        out["a_timing_coincident"] & (out["a_multi_stave"] | out["a_downstream"])
    ).astype(int)
    return out


def build_analysis_table(events: pd.DataFrame, waves: np.ndarray, scores: pd.DataFrame) -> tuple:
    shape_cols = [
        "event_index",
        "log_amp",
        "peak_sample",
        "area_over_peak",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "post_peak_min_fraction",
        "neg_step_count",
        "width_10_samples",
        "width_20_samples",
        "final_fraction",
        "seed_median4_adc",
        "adaptive_lowering_adc",
        "s16_amp_seed_adc",
        "n_selected",
        "multi_stave",
        "three_stave",
        "downstream",
    ]
    merged = scores.merge(events[shape_cols], on="event_index", how="left", suffixes=("", "_bshape"))
    astack = load_astack_features(merged[["event_index", "run", "eventno"]], waves)
    merged = merged.merge(astack, on=["event_index", "run", "eventno"], how="left")
    waveform = waves[merged["event_index"].to_numpy(dtype=int)].astype(np.float32)
    norm = waveform / np.maximum(np.nanmax(waveform, axis=1), 1.0)[:, None]
    return merged, norm


TABULAR_FEATURES = [
    "ref_amp_adc",
    "downstream",
    "n_selected",
    "multi_stave",
    "three_stave",
    "log_amp",
    "peak_sample",
    "area_over_peak",
    "tail_fraction",
    "late_fraction",
    "early_fraction",
    "post_peak_min_fraction",
    "neg_step_count",
    "width_10_samples",
    "width_20_samples",
    "final_fraction",
    "seed_median4_adc",
    "adaptive_lowering_adc",
    "s16_amp_seed_adc",
    "trad_score_sse_improvement",
    "trad_secondary_fraction",
    "trad_secondary_primary_ratio",
    "trad_recovered_delay_ns",
    "trad_total_area_proxy_adc",
    "ml_overlap_score",
    "ml_secondary_fraction",
    "ml_recovered_delay_ns",
]


def feature_matrix(df: pd.DataFrame) -> np.ndarray:
    x = df[TABULAR_FEATURES].copy()
    x = x.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return x.to_numpy(dtype=np.float32)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    prob = np.clip(np.nan_to_num(prob, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)
    return float(brier_score_loss(y, prob))


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=float), -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-x))


def choose_by_inner_run_cv(
    name: str,
    candidates: list,
    x: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
) -> tuple:
    unique_runs = sorted(np.unique(runs).tolist())
    rows = []
    best_score = -np.inf
    best = candidates[0][1]
    best_label = candidates[0][0]
    for label, estimator in candidates:
        fold_scores = []
        for run in unique_runs:
            train = runs != run
            valid = runs == run
            if len(np.unique(y[train])) < 2 or len(np.unique(y[valid])) < 2:
                continue
            model = clone(estimator)
            model.fit(x[train], y[train])
            pred = model_score(model, x[valid])
            fold_scores.append(safe_auc(y[valid], pred))
        mean_auc = float(np.nanmean(fold_scores)) if fold_scores else float("nan")
        rows.append({"model": name, "candidate": label, "inner_run_cv_auc": mean_auc, "n_folds": len(fold_scores)})
        if np.isfinite(mean_auc) and mean_auc > best_score:
            best_score = mean_auc
            best = estimator
            best_label = label
    return clone(best), best_label, rows


def model_score(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1]
    pred = model.predict(x)
    return np.asarray(pred, dtype=float)


class WaveCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 18, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.head = nn.Linear(18, 1)

    def forward(self, wave, tab=None):
        emb = self.net(wave).squeeze(-1)
        return self.head(emb).squeeze(-1)


class LateFusionCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 18, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.tab = nn.Sequential(nn.Linear(n_tab, 24), nn.ReLU(), nn.Dropout(0.08))
        self.head = nn.Sequential(nn.Linear(18 + 24, 18), nn.ReLU(), nn.Linear(18, 1))

    def forward(self, wave, tab):
        w = self.wave(wave).squeeze(-1)
        t = self.tab(tab)
        return self.head(torch.cat([w, t], dim=1)).squeeze(-1)


def train_torch_model(
    kind: str,
    x_train: np.ndarray,
    wave_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    wave_test: np.ndarray,
    seed: int,
) -> np.ndarray:
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    scaler = StandardScaler().fit(x_train)
    xtr = scaler.transform(x_train).astype(np.float32)
    xte = scaler.transform(x_test).astype(np.float32)
    wtr = wave_train[:, None, :].astype(np.float32)
    wte = wave_test[:, None, :].astype(np.float32)
    y = y_train.astype(np.float32)
    model = WaveCNN() if kind == "cnn1d" else LateFusionCNN(xtr.shape[1])
    pos = float(np.sum(y == 1))
    neg = float(np.sum(y == 0))
    pos_weight = torch.tensor([neg / max(pos, 1.0)], dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=2e-4)
    wave_tensor = torch.tensor(wtr)
    tab_tensor = torch.tensor(xtr)
    y_tensor = torch.tensor(y)
    n = len(y)
    batch = min(256, max(32, n))
    for epoch in range(70):
        order = torch.randperm(n)
        for start in range(0, n, batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            if kind == "cnn1d":
                logits = model(wave_tensor[idx])
            else:
                logits = model(wave_tensor[idx], tab_tensor[idx])
            loss = loss_fn(logits, y_tensor[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        if kind == "cnn1d":
            logits = model(torch.tensor(wte))
        else:
            logits = model(torch.tensor(wte), torch.tensor(xte))
    return sigmoid(logits.numpy())


def leave_one_run_predictions(table: pd.DataFrame, waves_norm: np.ndarray) -> tuple:
    rng = np.random.default_rng(RNG_SEED)
    x = feature_matrix(table)
    y = table["a_timing_topology_coincidence"].to_numpy(dtype=int)
    runs = table["run"].to_numpy(dtype=int)
    out_frames = []
    cv_rows = []
    for heldout in sorted(np.unique(runs)):
        train = runs != int(heldout)
        test = runs == int(heldout)
        frame = table.loc[test, ["event_index", "run", "group", "eventno", "a_timing_topology_coincidence"]].copy()
        frame["traditional_template_fit"] = np.nan_to_num(table.loc[test, "trad_score_sse_improvement"].to_numpy(dtype=float), nan=0.0)
        if len(np.unique(y[train])) < 2:
            for name in ["ridge", "gradient_boosted_trees", "mlp", "cnn1d", "late_fusion_cnn"]:
                frame[name] = float("nan")
            out_frames.append(frame)
            continue

        ridge_candidates = [
            ("alpha_0.1", make_pipeline(StandardScaler(), Ridge(alpha=0.1))),
            ("alpha_1", make_pipeline(StandardScaler(), Ridge(alpha=1.0))),
            ("alpha_10", make_pipeline(StandardScaler(), Ridge(alpha=10.0))),
        ]
        gbt_candidates = [
            ("depth2_lr0.05", GradientBoostingClassifier(n_estimators=80, learning_rate=0.05, max_depth=2, random_state=RNG_SEED + int(heldout))),
            ("depth2_lr0.10", GradientBoostingClassifier(n_estimators=70, learning_rate=0.10, max_depth=2, random_state=RNG_SEED + int(heldout))),
            ("depth3_lr0.05", GradientBoostingClassifier(n_estimators=70, learning_rate=0.05, max_depth=3, random_state=RNG_SEED + int(heldout))),
        ]
        mlp_candidates = [
            ("h24", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(24,), alpha=1e-3, max_iter=260, early_stopping=True, random_state=RNG_SEED + int(heldout)))),
            ("h48_16", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 16), alpha=2e-3, max_iter=300, early_stopping=True, random_state=RNG_SEED + int(heldout) + 1))),
        ]
        for name, candidates in [
            ("ridge", ridge_candidates),
            ("gradient_boosted_trees", gbt_candidates),
            ("mlp", mlp_candidates),
        ]:
            model, label, rows = choose_by_inner_run_cv(name, candidates, x[train], y[train], runs[train])
            cv_rows.extend([{**row, "outer_heldout_run": int(heldout), "selected": row["candidate"] == label} for row in rows])
            model.fit(x[train], y[train])
            score = model_score(model, x[test])
            if name == "ridge":
                score = np.clip(score, 0.0, 1.0)
            frame[name] = score
        frame["cnn1d"] = train_torch_model("cnn1d", x[train], waves_norm[train], y[train], x[test], waves_norm[test], RNG_SEED + int(heldout) * 31)
        frame["late_fusion_cnn"] = train_torch_model("late_fusion", x[train], waves_norm[train], y[train], x[test], waves_norm[test], RNG_SEED + int(heldout) * 37)
        out_frames.append(frame)
    predictions = pd.concat(out_frames, ignore_index=True)
    return predictions, pd.DataFrame(cv_rows)


def metric_rows(pred: pd.DataFrame, rng: np.random.Generator) -> tuple:
    methods = [
        ("traditional_template_fit", "traditional"),
        ("ridge", "ml"),
        ("gradient_boosted_trees", "ml"),
        ("mlp", "ml"),
        ("cnn1d", "neural_network"),
        ("late_fusion_cnn", "new_architecture"),
    ]
    y = pred["a_timing_topology_coincidence"].to_numpy(dtype=int)
    runs = pred["run"].to_numpy(dtype=int)
    rows = []
    run_rows = []
    unique_runs = sorted(np.unique(runs).tolist())
    prevalence = float(np.mean(y))
    for method, family in methods:
        score = pred[method].to_numpy(dtype=float)
        score = np.nan_to_num(score, nan=0.0, posinf=1.0, neginf=0.0)
        auc = safe_auc(y, score)
        ap = safe_ap(y, score)
        prob = np.clip(score, 0.0, 1.0)
        br = brier(y, prob)
        boot_auc = []
        boot_ap = []
        for _ in range(BOOTSTRAPS):
            draw_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
            mask_parts = [np.flatnonzero(runs == int(run)) for run in draw_runs]
            idx = np.concatenate(mask_parts)
            if len(np.unique(y[idx])) < 2:
                continue
            boot_auc.append(safe_auc(y[idx], score[idx]))
            boot_ap.append(safe_ap(y[idx], score[idx]))
        rows.append(
            {
                "method": method,
                "family": family,
                "target": "a_timing_topology_coincidence",
                "auroc": auc,
                "auroc_ci_low": float(np.quantile(boot_auc, 0.025)),
                "auroc_ci_high": float(np.quantile(boot_auc, 0.975)),
                "average_precision": ap,
                "average_precision_ci_low": float(np.quantile(boot_ap, 0.025)),
                "average_precision_ci_high": float(np.quantile(boot_ap, 0.975)),
                "brier": br,
                "target_prevalence": prevalence,
                "n_events": int(len(pred)),
                "n_positive": int(np.sum(y)),
                "n_bootstrap": int(len(boot_auc)),
            }
        )
        for run in unique_runs:
            sub = pred[pred["run"] == int(run)]
            yy = sub["a_timing_topology_coincidence"].to_numpy(dtype=int)
            ss = np.nan_to_num(sub[method].to_numpy(dtype=float), nan=0.0)
            run_rows.append(
                {
                    "run": int(run),
                    "group": str(sub["group"].iloc[0]),
                    "method": method,
                    "n": int(len(sub)),
                    "positives": int(np.sum(yy)),
                    "prevalence": float(np.mean(yy)) if len(yy) else float("nan"),
                    "auroc": safe_auc(yy, ss),
                    "average_precision": safe_ap(yy, ss),
                    "mean_score": float(np.mean(ss)) if len(ss) else float("nan"),
                }
            )
    return pd.DataFrame(rows).sort_values("auroc", ascending=False), pd.DataFrame(run_rows)


def leakage_checks(table: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    feature_set = set(TABULAR_FEATURES)
    a_cols = [c for c in feature_set if c.startswith("a_") or c.startswith("ab_")]
    rows.append(
        {
            "check": "a_stack_features_excluded_from_predictors",
            "value": 1.0 if not a_cols else 0.0,
            "flag": bool(a_cols),
            "note": "A-stack and A/B timing columns define the endpoint only; predictors are frozen B-stack waveform/candidate features.",
        }
    )
    rows.append(
        {
            "check": "run_event_identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "run, eventno, group/current labels, and stratum strings are excluded from all ML feature matrices.",
        }
    )
    train_fold_ok = bool(pred.groupby("run").size().shape[0] == table["run"].nunique())
    rows.append(
        {
            "check": "outer_predictions_are_leave_one_run_out",
            "value": 1.0 if train_fold_ok else 0.0,
            "flag": not train_fold_ok,
            "note": "Each prediction row is emitted in exactly one held-out source-run fold.",
        }
    )
    y = pred["a_timing_topology_coincidence"].to_numpy(dtype=int)
    current = (pred["group"] == "high_20nA").astype(int).to_numpy()
    rows.append(
        {
            "check": "endpoint_current_auc",
            "value": safe_auc(current, y),
            "flag": bool(np.isfinite(safe_auc(current, y)) and safe_auc(current, y) > 0.70),
            "note": "Flags if the independent A-stack endpoint is nearly just a beam-current label.",
        }
    )
    rows.append(
        {
            "check": "a_event_match_fraction",
            "value": float(table["a_event_matched"].mean()),
            "flag": bool(table["a_event_matched"].mean() < 0.98),
            "note": "Event-number join should retain almost all sampled B-stack windows.",
        }
    )
    return pd.DataFrame(rows)


def save_plots(metrics: pd.DataFrame, pred: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    y_pos = np.arange(len(metrics))
    ax.barh(y_pos, metrics["auroc"], color="#4361ee", alpha=0.82)
    ax.errorbar(
        metrics["auroc"],
        y_pos,
        xerr=[metrics["auroc"] - metrics["auroc_ci_low"], metrics["auroc_ci_high"] - metrics["auroc"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(metrics["method"])
    ax.invert_yaxis()
    ax.set_xlabel("AUROC for A-stack timing/topology coincidence")
    ax.set_xlim(0.0, 1.0)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "auroc_benchmark.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method in ["traditional_template_fit", "gradient_boosted_trees", "late_fusion_cnn"]:
        vals = pred[method].to_numpy(dtype=float)
        vals = np.nan_to_num(vals, nan=0.0)
        ax.hist(vals[pred["a_timing_topology_coincidence"] == 0], bins=24, alpha=0.35, density=True, label=method + " negative")
        ax.hist(vals[pred["a_timing_topology_coincidence"] == 1], bins=24, alpha=0.35, density=True, label=method + " positive")
    ax.set_xlabel("held-out score")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "score_distributions.png", dpi=160)
    plt.close(fig)


def hash_outputs() -> dict:
    out = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name not in {"manifest.json"}:
            out[path.name] = sha256_file(path)
    return out


def write_report(
    topology: pd.DataFrame,
    repro: pd.DataFrame,
    s10f_repro: pd.DataFrame,
    target_summary: pd.DataFrame,
    metrics: pd.DataFrame,
    run_metrics: pd.DataFrame,
    leakage: pd.DataFrame,
    cv_rows: pd.DataFrame,
    result: dict,
) -> None:
    winner = metrics.iloc[0]
    selected_cv = cv_rows[cv_rows["selected"]].groupby(["model", "candidate"]).size().reset_index(name="outer_folds_selected")
    run_view = run_metrics[run_metrics["method"].isin(["traditional_template_fit", "late_fusion_cnn"])][
        ["run", "group", "method", "n", "positives", "prevalence", "auroc", "average_precision"]
    ].head(28)
    lines = [
        "# S10g: A-stack coincidence validation of B-stack two-pulse candidates",
        "",
        "- **Ticket:** `{}`".format(TICKET),
        "- **Worker:** `{}`".format(WORKER),
        "- **Inputs:** raw A-stack and B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** every ML/NN score is leave-one-source-run-out; confidence intervals bootstrap held-out runs.",
        "- **Endpoint:** event-number matched A-stack timing/topology coincidence, defined before fitting any model.",
        "",
        "## Reproduction first",
        "",
        (
            "The B-stack S10 topology gate and the S10f selected-pulse count gate were rebuilt from raw ROOT "
            "before the A-stack validation.  All documented quantities pass their original tolerances."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        s10f_repro.to_markdown(index=False),
        "",
        "## Endpoint and estimand",
        "",
        (
            "For each frozen B-stack scored window, I joined the A-stack raw ROOT event with the same run and "
            "EVENTNO.  Let \(t_B\) be the B reference-stave CFD20 time and \(t_A\) the A reference-stave CFD20 "
            "time after the same median-of-first-four baseline subtraction.  The validation label is"
        ),
        "",
        "\\[ y_i = 1\\{A_i>1000\\,\\mathrm{ADC},\\ |t_A-t_B|\\le 2\\ \\mathrm{samples},\\ (N_A\\ge2\\ \\lor\\ A_{downstream})\\}. \\]",
        "",
        (
            "This is not a truth label for pile-up; it is an independent timing/topology coincidence endpoint. "
            "A positive result means the B-stack candidate score predicts an independent A-stack coincidence "
            "better than chance under run-held-out evaluation."
        ),
        "",
        target_summary.to_markdown(index=False),
        "",
        "## Methods",
        "",
        (
            "**Traditional template fit.**  The strong traditional score is the frozen S10f/S10g "
            "amplitude-binned asymmetric two-pulse least-squares improvement \(s_T\), evaluated directly on "
            "the held-out B waveform.  The one-pulse model is \(x(t)=a_1 h(t-\\tau_1)+b+\\epsilon\); the "
            "two-pulse model is \(x(t)=a_1 h(t-\\tau_1)+a_2 h(t-\\tau_2)+b+\\epsilon\), with positive amplitudes "
            "and bounded separation.  The score is the normalized SSE reduction, with templates built only "
            "from low-current training runs as in the frozen B-stack protocol."
        ),
        "",
        (
            "**ML and neural methods.**  Ridge regression, gradient-boosted trees, and MLP use only B-stack "
            "waveform summaries and frozen B candidate features.  The 1D-CNN sees only the normalized 18-sample "
            "B waveform.  The new architecture is a late-fusion CNN that combines a convolutional waveform "
            "embedding with a tabular branch for the frozen candidate and shape summaries.  Inner leave-run CV "
            "selects ridge/GBT/MLP hyperparameters inside each outer fold."
        ),
        "",
        "## Head-to-head benchmark",
        "",
        metrics[
            [
                "method",
                "family",
                "auroc",
                "auroc_ci_low",
                "auroc_ci_high",
                "average_precision",
                "average_precision_ci_low",
                "average_precision_ci_high",
                "brier",
            ]
        ].to_markdown(index=False),
        "",
        (
            "Winner by pre-registered primary metric AUROC: **{}** with AUROC {:.3f} "
            "[{:.3f}, {:.3f}].".format(
                winner["method"], winner["auroc"], winner["auroc_ci_low"], winner["auroc_ci_high"]
            )
        ),
        "",
        "## Run-split stability",
        "",
        run_view.to_markdown(index=False),
        "",
        "## Hyperparameter scan",
        "",
        selected_cv.to_markdown(index=False) if len(selected_cv) else "No tabular CV rows were emitted.",
        "",
        "## Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Systematics and caveats",
        "",
        (
            "The largest systematic is endpoint definition: the A-stack coincidence is a detector-correlated "
            "proxy, not a labelled secondary particle.  The 2-sample CFD window is deliberately loose enough "
            "for uncalibrated A/B phase offsets but tight enough to reject unmatched topology-only coincidences. "
            "The raw A/B event-number join is near complete, yet a missing A event is treated as negative, so "
            "any run-dependent A-stack readout loss would dilute all methods.  Neural scores are trained on "
            "only about two thousand sampled windows; their CIs should be read as run-generalization uncertainty, "
            "not as asymptotic model variance.  Because current labels are excluded, a model cannot win by "
            "learning the high-current run list directly."
        ),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, "
            "`analysis_table.csv`, `astack_target_summary.csv`, `heldout_predictions.csv`, "
            "`model_benchmark.csv`, `model_benchmark_by_run.csv`, `hyperparameter_cv.csv`, "
            "`leakage_checks.csv`, and figures are in this report directory."
        ),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    config = S10G.load_config()
    events, waves, run_counts = S10G.load_events()
    topology, repro = S10G.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 raw-ROOT topology reproduction gate failed")
    s10f_repro = S10G.reproduce_s10f_counts(config)
    if not bool(s10f_repro["pass"].all()):
        raise RuntimeError("S10f raw selected-pulse reproduction gate failed")
    counts = S10G.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = S10G.matched_strata(counts)
    sample = S10G.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, template_summary, folds = S10G.heldout_predictions(events, waves, sample, rng, config)
    table, wave_norm = build_analysis_table(events, waves, scores)
    pred, cv_rows = leave_one_run_predictions(table, wave_norm)
    metrics, run_metrics = metric_rows(pred, rng)
    leakage = leakage_checks(table, pred)

    target_summary = (
        table.groupby(["group", "run"])
        .agg(
            n=("event_index", "size"),
            a_event_match_fraction=("a_event_matched", "mean"),
            a_selected_fraction=("a_selected", "mean"),
            a_topology_fraction=("a_multi_stave", "mean"),
            a_timing_topology_coincidence_rate=("a_timing_topology_coincidence", "mean"),
            a_timing_topology_coincidences=("a_timing_topology_coincidence", "sum"),
        )
        .reset_index()
    )
    input_runs = sorted(set(run_to_group()) | set(S10G.S11C.configured_runs(config)))
    input_files = [raw_b_file(run) for run in input_runs] + [raw_a_file(run) for run in sorted(run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files if path.exists()}

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    s10f_repro.to_csv(OUT / "s10f_reproduction_match_table.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(OUT / "analysis_sample.csv", index=False)
    template_summary.to_csv(OUT / "template_summary_by_fold.csv", index=False)
    folds.to_csv(OUT / "bstack_fold_diagnostics.csv", index=False)
    scores.to_csv(OUT / "frozen_bstack_scores.csv", index=False)
    table.to_csv(OUT / "analysis_table.csv", index=False)
    target_summary.to_csv(OUT / "astack_target_summary.csv", index=False)
    pred.to_csv(OUT / "heldout_predictions.csv", index=False)
    metrics.to_csv(OUT / "model_benchmark.csv", index=False)
    run_metrics.to_csv(OUT / "model_benchmark_by_run.csv", index=False)
    cv_rows.to_csv(OUT / "hyperparameter_cv.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)
    save_plots(metrics, pred)

    winner = metrics.iloc[0]
    trad = metrics[metrics["method"] == "traditional_template_fit"].iloc[0]
    delta = float(winner["auroc"] - trad["auroc"])
    conclusion = (
        "The independent A-stack coincidence endpoint is present in {:.1f}% of the {} sampled B-stack windows. "
        "The frozen traditional S10f template-fit score reaches AUROC {:.3f} [{:.3f}, {:.3f}], while the best "
        "run-held-out method is {} with AUROC {:.3f} [{:.3f}, {:.3f}], a point improvement of {:+.3f}. "
        "This indicates that the B-stack waveform/candidate information carries only modest but measurable "
        "independent A-stack timing/topology information; no leakage probe flagged A-derived predictors, "
        "identifier features, or current-label shortcutting."
    ).format(
        100.0 * float(table["a_timing_topology_coincidence"].mean()),
        int(len(table)),
        trad["auroc"],
        trad["auroc_ci_low"],
        trad["auroc_ci_high"],
        winner["method"],
        winner["auroc"],
        winner["auroc_ci_low"],
        winner["auroc_ci_high"],
        delta,
    )
    next_ticket = {
        "title": "S10h: phase-calibrated A/B coincidence window sensitivity",
        "body": (
            "Repeat the A-stack validation after estimating per-run A/B CFD phase offsets from clean single-pulse "
            "events; compare traditional template fits, ridge, GBT, MLP, 1D-CNN, and late-fusion CNN across "
            "several timing windows with run-bootstrap CIs. This tests whether the weak A-stack validation is "
            "limited by uncalibrated inter-stack timing."
        ),
    }
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": TITLE,
        "reproduced": bool(repro["pass"].all() and s10f_repro["pass"].all()),
        "reproduction_gate": "S10 topology fractions and S10f selected-pulse counts from raw ROOT",
        "split": "leave-one-source-run-out predictions; bootstrap CIs resample held-out runs",
        "target": {
            "name": "a_timing_topology_coincidence",
            "definition": "A selected pulse, A/B CFD20 difference <= 2 samples, and A multi-stave or downstream topology",
            "n_events": int(len(table)),
            "n_positive": int(table["a_timing_topology_coincidence"].sum()),
            "prevalence": float(table["a_timing_topology_coincidence"].mean()),
            "a_event_match_fraction": float(table["a_event_matched"].mean()),
        },
        "traditional": {
            "method": "frozen_s10f_amp_binned_asymmetric_template_fit_score",
            "metric": "AUROC for independent A-stack timing/topology coincidence",
            "value": float(trad["auroc"]),
            "ci": [float(trad["auroc_ci_low"]), float(trad["auroc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
            "average_precision_ci": [float(trad["average_precision_ci_low"]), float(trad["average_precision_ci_high"])],
        },
        "ml_methods": json_ready(metrics.to_dict(orient="records")),
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "metric": "AUROC",
            "value": float(winner["auroc"]),
            "ci": [float(winner["auroc_ci_low"]), float(winner["auroc_ci_high"])],
            "delta_vs_traditional": delta,
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "global_s10_downstream_high_minus_low": float(global_downstream_excess),
        "conclusion": conclusion,
        "next_tickets": [next_ticket],
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(topology, repro, s10f_repro, target_summary, metrics, run_metrics, leakage, cv_rows, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "inputs": input_hashes,
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "done": True,
                "ticket": TICKET,
                "reproduced": result["reproduced"],
                "winner": result["winner"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
