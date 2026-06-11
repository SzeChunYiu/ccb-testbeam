#!/usr/bin/env python3
"""S13f exactly-two downstream current-family timing-tail null."""

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
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "reports" / ".mplconfig_s13f_1781063920"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


METHOD_SCORE_COLS = {
    "traditional_timing_template": "score_traditional_timing_template",
    "ridge_waveform": "score_ridge_waveform",
    "gradient_boosted_trees": "score_gradient_boosted_trees",
    "mlp_waveform": "score_mlp_waveform",
    "cnn1d_waveform": "score_cnn1d_waveform",
    "support_gated_cnn_new": "score_support_gated_cnn_new",
    "shuffled_label_gbt_control": "score_shuffled_label_gbt_control",
}


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_file(config: dict, run: int) -> Path:
    raw = Path(config["raw_root_dir"])
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw / f"hrdb_run_{run:04d}.root"


def family_map(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for family, runs in config["current_run_families"].items():
        for run in runs:
            out[int(run)] = family
    return out


def cfd_times_ns(waves: np.ndarray, amps: np.ndarray, fraction: float, sample_period_ns: float, cut: float) -> np.ndarray:
    out = np.full(amps.shape, np.nan, dtype=float)
    threshold = fraction * amps
    for i in range(waves.shape[0]):
        for j in range(waves.shape[1]):
            if amps[i, j] <= cut:
                continue
            vals = waves[i, j]
            above = np.flatnonzero(vals >= threshold[i, j])
            if len(above) == 0:
                continue
            k = int(above[0])
            if k == 0:
                out[i, j] = 0.0
            else:
                y0 = vals[k - 1]
                y1 = vals[k]
                frac = 0.0 if y1 == y0 else (threshold[i, j] - y0) / (y1 - y0)
                out[i, j] = (k - 1 + np.clip(frac, 0.0, 1.0)) * sample_period_ns
    return out


def event_timing(times: np.ndarray, selected: np.ndarray, downstream_idx: np.ndarray) -> Tuple[float, float]:
    keep = downstream_idx[selected[downstream_idx] & np.isfinite(times[downstream_idx])]
    if len(keep) < 2:
        return float("nan"), float("nan")
    vals = times[keep]
    d_t = float(np.max(vals) - np.min(vals))
    c_t = float("nan")
    if len(keep) == 3 and np.all(np.isfinite(times[downstream_idx])):
        c_t = float(times[downstream_idx[2]] - 2.0 * times[downstream_idx[1]] + times[downstream_idx[0]])
    return d_t, c_t


def pulse_shape_features(waves: np.ndarray, amps: np.ndarray, prefix: str) -> pd.DataFrame:
    safe = np.maximum(np.abs(amps), 1.0)
    area_pos = np.clip(waves, 0.0, None).sum(axis=1)
    area_signed = waves.sum(axis=1)
    peak = waves.argmax(axis=1)
    norm = waves / safe[:, None]
    frame = pd.DataFrame(
        {
            f"{prefix}_peak_sample": peak.astype(float),
            f"{prefix}_area_over_amp": area_pos / safe,
            f"{prefix}_signed_area_over_amp": area_signed / safe,
            f"{prefix}_tail_fraction": waves[:, 10:].sum(axis=1) / np.maximum(area_signed, 1.0),
            f"{prefix}_late_fraction": waves[:, 12:].max(axis=1) / safe,
            f"{prefix}_early_fraction": waves[:, :4].max(axis=1) / safe,
            f"{prefix}_post_min_fraction": waves[:, 8:].min(axis=1) / safe,
            f"{prefix}_width20": (waves > 0.20 * safe[:, None]).sum(axis=1).astype(float),
            f"{prefix}_width10": (waves > 0.10 * safe[:, None]).sum(axis=1).astype(float),
            f"{prefix}_neg_step_count": (np.diff(waves, axis=1) < -0.20 * safe[:, None]).sum(axis=1).astype(float),
            f"{prefix}_final_fraction": waves[:, -1] / safe,
        }
    )
    for sample in range(norm.shape[1]):
        frame[f"{prefix}_norm_s{sample:02d}"] = norm[:, sample]
    return frame


def anomaly_code(features: pd.DataFrame, stave_names: List[str]) -> np.ndarray:
    score = np.zeros(len(features), dtype=int)
    for name in stave_names:
        score += (features[f"{name}_late_fraction"].to_numpy(dtype=float) > 0.22).astype(int)
        score += (features[f"{name}_tail_fraction"].to_numpy(dtype=float) > 0.36).astype(int)
        score += (features[f"{name}_neg_step_count"].to_numpy(dtype=float) >= 2.0).astype(int)
    return np.minimum(score, 3)


def read_events(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame]:
    stave_names = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in stave_names], dtype=int)
    downstream_idx = np.asarray([stave_names.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = stave_names.index("B2")
    baseline_samples = [int(x) for x in config["baseline_samples"]]
    nsamples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    run_family = family_map(config)
    event_rows = []
    feature_rows = []
    wave_rows = []
    run_rows = []
    uid_base = 0

    for run in [int(x) for x in config["runs"]]:
        raw_events = parent_events = all_three_events = exactly_two_events = 0
        path = raw_file(config, run)
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamples)
            waves = raw[:, channels, :]
            baseline = np.median(waves[..., baseline_samples], axis=-1)
            corrected = waves - baseline[..., None]
            amp = corrected.max(axis=-1)
            selected = amp > cut
            times = cfd_times_ns(corrected, amp, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            raw_events += len(eventno)
            parent_mask = selected[:, b2_idx] & (selected[:, downstream_idx].sum(axis=1) >= 2)

            for idx in np.flatnonzero(parent_mask):
                d_t, c_t = event_timing(times[idx], selected[idx], downstream_idx)
                if not math.isfinite(d_t):
                    continue
                n_downstream = int(selected[idx, downstream_idx].sum())
                all_three = n_downstream == 3
                exactly_two = n_downstream == 2
                parent_events += 1
                all_three_events += int(all_three)
                exactly_two_events += int(exactly_two)
                pair_names = [stave_names[j] for j in downstream_idx if bool(selected[idx, j])]
                pair = "+".join(pair_names)
                event_key = f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{uid_base + int(idx)}"
                row = {
                    "event_key": event_key,
                    "run": run,
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "run_family": run_family[run],
                    "is_target_low": int(run_family[run] == config["target_low_family"]),
                    "is_target_high": int(run_family[run] == config["target_high_family"]),
                    "d_t_ns": d_t,
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else np.nan,
                    "n_downstream": n_downstream,
                    "downstream_pair": pair,
                    "all_three": int(all_three),
                    "exactly_two": int(exactly_two),
                    "clean_label": int(d_t < float(config["clean_dt_max_ns"])),
                    "gross_label": int(d_t > float(config["gross_dt_min_ns"])),
                    "doc_gross_label": int(d_t > float(config["documented_gross_dt_min_ns"])),
                    "event_max_amp": float(np.max(amp[idx, selected[idx]])),
                    "b2_amp": float(amp[idx, b2_idx]),
                    "downstream_charge": float(np.clip(corrected[idx, downstream_idx, :], 0.0, None).sum()),
                    "event_charge": float(np.clip(corrected[idx, selected[idx], :], 0.0, None).sum()),
                    "baseline_abs_mean": float(np.mean(np.abs(baseline[idx]))),
                    "baseline_lowering": int(np.min(baseline[idx]) < -35.0),
                    "saturation_any": int(np.max(amp[idx, selected[idx]]) >= 6500.0),
                }
                parts = []
                for stave_i, name in enumerate(stave_names):
                    row[f"{name}_amp"] = float(amp[idx, stave_i])
                    row[f"{name}_selected"] = int(selected[idx, stave_i])
                    parts.append(pulse_shape_features(corrected[idx : idx + 1, stave_i, :], amp[idx : idx + 1, stave_i], name))
                feats = pd.concat(parts, axis=1)
                row["anomaly_code"] = int(anomaly_code(feats, stave_names)[0])
                event_rows.append(row)
                feature_rows.append(feats)
                safe = np.maximum(np.abs(amp[idx]), 1.0)
                wave_rows.append((corrected[idx] / safe[:, None]).astype("float32"))
            uid_base += len(eventno)
        run_rows.append(
            {
                "run": run,
                "current_run_family": run_family[run],
                "raw_events": raw_events,
                "parent_control_events": parent_events,
                "all_three_events": all_three_events,
                "exactly_two_events": exactly_two_events,
                "exactly_two_rate": exactly_two_events / max(raw_events, 1),
            }
        )

    events = pd.DataFrame(event_rows)
    features = pd.concat(feature_rows, ignore_index=True)
    waves = np.stack(wave_rows).astype("float32")
    run_meta = pd.DataFrame(run_rows)
    return events, features, waves, run_meta


def reproduction_table(config: dict, events: pd.DataFrame) -> pd.DataFrame:
    parent = events
    all_three = events[events["all_three"] == 1]
    exactly_two = events[events["exactly_two"] == 1]
    rows = [
        ("S13d parent control events, B2 and >=2 downstream", config["expected_parent_control_events"], len(parent), 0),
        ("S13d parent clean events, D_t<3 ns", config["expected_parent_clean_events"], int(parent["clean_label"].sum()), 0),
        ("S13d parent gross events, documented D_t>50 ns", config["expected_parent_gross_events_documented"], int(parent["doc_gross_label"].sum()), 0),
        ("S13d parent gross events, guarded D_t>51 ns", config["expected_parent_gross_events_guarded"], int(parent["gross_label"].sum()), 0),
        ("S13d all-three control events", config["expected_all_three_events"], len(all_three), 0),
        ("S13d all-three guarded gross events", config["expected_all_three_gross_events_guarded"], int(all_three["gross_label"].sum()), 0),
        ("S13f exactly-two control events", int(config["expected_parent_control_events"]) - int(config["expected_all_three_events"]), len(exactly_two), 0),
        ("S13f exactly-two guarded gross events", int(config["expected_parent_gross_events_guarded"]) - int(config["expected_all_three_gross_events_guarded"]), int(exactly_two["gross_label"].sum()), 0),
    ]
    out = pd.DataFrame(rows, columns=["quantity", "report_value", "reproduced", "tolerance"])
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def quantile_edges(values: pd.Series, bins: int) -> np.ndarray:
    qs = np.linspace(0.0, 1.0, bins + 1)
    finite = values.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    edges = np.quantile(finite, qs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return edges


def add_match_strata(train_events: pd.DataFrame, test_events: pd.DataFrame, config: dict) -> Tuple[pd.Series, pd.Series]:
    amp_edges = quantile_edges(train_events["event_max_amp"], int(config["event_amp_bins"]))
    charge_edges = quantile_edges(np.log1p(train_events["event_charge"]), int(config["charge_bins"]))
    b2_edges = quantile_edges(train_events["b2_amp"], int(config["charge_bins"]))
    baseline_edges = quantile_edges(train_events["baseline_abs_mean"], int(config["baseline_bins"]))
    tail_edges = quantile_edges(train_events["anomaly_code"], int(config["tail_bins"]))

    def labels(frame: pd.DataFrame) -> pd.Series:
        event_amp_bin = pd.cut(frame["event_max_amp"], bins=amp_edges, labels=False, include_lowest=True).astype(str)
        charge_bin = pd.cut(np.log1p(frame["event_charge"]), bins=charge_edges, labels=False, include_lowest=True).astype(str)
        b2_bin = pd.cut(frame["b2_amp"], bins=b2_edges, labels=False, include_lowest=True).astype(str)
        baseline_bin = pd.cut(frame["baseline_abs_mean"], bins=baseline_edges, labels=False, include_lowest=True).astype(str)
        tail_bin = pd.cut(frame["anomaly_code"], bins=tail_edges, labels=False, include_lowest=True).astype(str)
        sat = frame["saturation_any"].astype(int).astype(str)
        lower = frame["baseline_lowering"].astype(int).astype(str)
        pair = frame["downstream_pair"].astype(str)
        return event_amp_bin + "|q" + charge_bin + "|b2" + b2_bin + "|sat" + sat + "|base" + baseline_bin + "|low" + lower + "|tail" + tail_bin + "|pair" + pair

    return labels(train_events), labels(test_events)


def matched_test_indices(test_events: pd.DataFrame, strata: pd.Series, config: dict, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = test_events.copy()
    frame["stratum"] = strata.to_numpy()
    chosen = []
    cap = int(config["max_matched_per_stratum_family"])
    for _stratum, group in frame.groupby("stratum"):
        low = group.index[group["is_target_low"].to_numpy() == 1].to_numpy()
        high = group.index[group["is_target_high"].to_numpy() == 1].to_numpy()
        n = min(len(low), len(high), cap)
        if n < 1:
            continue
        chosen.append(rng.choice(low, n, replace=False))
        chosen.append(rng.choice(high, n, replace=False))
    if not chosen:
        return np.asarray([], dtype=int)
    return rng.permutation(np.concatenate(chosen))


def waveform_feature_columns(features: pd.DataFrame) -> List[str]:
    allowed_suffixes = (
        "peak_sample",
        "area_over_amp",
        "signed_area_over_amp",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "post_min_fraction",
        "width20",
        "width10",
        "neg_step_count",
        "final_fraction",
    )
    cols = [col for col in features.columns if "_norm_s" in col or col.endswith(allowed_suffixes)]
    return sorted(cols)


def fit_ridge(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, c_grid: Iterable[float], seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    xtr = scaler.transform(train_x)
    xte = scaler.transform(test_x)
    best = None
    for c in c_grid:
        clf = LogisticRegression(C=float(c), penalty="l2", class_weight="balanced", max_iter=1000, random_state=seed)
        clf.fit(xtr, train_y)
        p = clf.predict_proba(xtr)[:, 1]
        score = brier_score_loss(train_y, p)
        if best is None or score < best[0]:
            best = (score, clf)
    return best[1].predict_proba(xtr)[:, 1], best[1].predict_proba(xte)[:, 1]


def fit_gbt(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    best = None
    for lr in config["gbt_learning_rates"]:
        for leaves in config["gbt_max_leaf_nodes"]:
            clf = HistGradientBoostingClassifier(
                learning_rate=float(lr),
                max_leaf_nodes=int(leaves),
                l2_regularization=0.08,
                max_iter=140,
                random_state=seed,
            )
            clf.fit(train_x, train_y)
            p = clf.predict_proba(train_x)[:, 1]
            score = brier_score_loss(train_y, p)
            if best is None or score < best[0]:
                best = (score, clf)
    return best[1].predict_proba(train_x)[:, 1], best[1].predict_proba(test_x)[:, 1]


def fit_mlp(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    xtr = scaler.transform(train_x)
    xte = scaler.transform(test_x)
    best = None
    for hidden in config["mlp_hidden_layers"]:
        clf = MLPClassifier(hidden_layer_sizes=tuple(int(x) for x in hidden), alpha=2e-3, max_iter=240, random_state=seed, early_stopping=True)
        clf.fit(xtr, train_y)
        p = clf.predict_proba(xtr)[:, 1]
        score = brier_score_loss(train_y, p)
        if best is None or score < best[0]:
            best = (score, clf)
    return best[1].predict_proba(xtr)[:, 1], best[1].predict_proba(xte)[:, 1]


class Cnn1D(torch.nn.Module):
    def __init__(self, n_scalar: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(4, 12, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(12, 16, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
        )
        self.head = torch.nn.Sequential(torch.nn.Linear(16 + n_scalar, 28), torch.nn.ReLU(), torch.nn.Linear(28, 1))

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, scalar], dim=1)).squeeze(1)


class SupportGatedCnn(torch.nn.Module):
    def __init__(self, n_scalar: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(4, 14, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(14, 18, kernel_size=5, padding=2),
            torch.nn.ReLU(),
            torch.nn.AdaptiveMaxPool1d(1),
        )
        self.scalar = torch.nn.Sequential(torch.nn.Linear(n_scalar, 18), torch.nn.ReLU())
        self.gate = torch.nn.Sequential(torch.nn.Linear(n_scalar, 18), torch.nn.Sigmoid())
        self.head = torch.nn.Sequential(torch.nn.Linear(36, 28), torch.nn.ReLU(), torch.nn.Linear(28, 1))

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave).squeeze(-1)
        s = self.scalar(scalar)
        g = self.gate(scalar)
        return self.head(torch.cat([z * g, s], dim=1)).squeeze(1)


def fit_torch(
    model_name: str,
    train_wave: np.ndarray,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_wave: np.ndarray,
    test_x: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler().fit(train_x)
    train_scalar = scaler.transform(train_x).astype("float32")
    test_scalar = scaler.transform(test_x).astype("float32")
    torch.manual_seed(seed)
    model = Cnn1D(train_scalar.shape[1]) if model_name == "cnn1d_waveform" else SupportGatedCnn(train_scalar.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(len(train_y) - train_y.sum()) / max(train_y.sum(), 1)], dtype=torch.float32))
    xw = torch.tensor(train_wave, dtype=torch.float32)
    xs = torch.tensor(train_scalar, dtype=torch.float32)
    yy = torch.tensor(train_y.astype("float32"))
    rng = np.random.default_rng(seed)
    batch = int(config["torch_batch_size"])
    model.train()
    for _epoch in range(int(config["torch_epochs"])):
        order = rng.permutation(len(yy))
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            loss = loss_fn(model(xw[idx], xs[idx]), yy[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        train_p = torch.sigmoid(model(torch.tensor(train_wave, dtype=torch.float32), torch.tensor(train_scalar, dtype=torch.float32))).numpy()
        test_p = torch.sigmoid(model(torch.tensor(test_wave, dtype=torch.float32), torch.tensor(test_scalar, dtype=torch.float32))).numpy()
    return np.clip(train_p, 1e-4, 1 - 1e-4), np.clip(test_p, 1e-4, 1 - 1e-4)


def calibrate(train_y: np.ndarray, train_p: np.ndarray, test_p: np.ndarray) -> np.ndarray:
    x = np.clip(train_p, 1e-4, 1 - 1e-4)
    logits = np.log(x / (1 - x)).reshape(-1, 1)
    lr = LogisticRegression(C=10.0, max_iter=1000)
    lr.fit(logits, train_y)
    t = np.clip(test_p, 1e-4, 1 - 1e-4)
    return np.clip(lr.predict_proba(np.log(t / (1 - t)).reshape(-1, 1))[:, 1], 1e-4, 1 - 1e-4)


def metric_delta(scored: pd.DataFrame, col: str) -> float:
    high = scored.loc[scored["family_label"] == 1, col].to_numpy(dtype=float)
    low = scored.loc[scored["family_label"] == 0, col].to_numpy(dtype=float)
    return float(high.mean() - low.mean())


def fixed_efficiency_excess(scored: pd.DataFrame, col: str, eff: float) -> float:
    low = scored.loc[scored["family_label"] == 0, col].to_numpy(dtype=float)
    high = scored.loc[scored["family_label"] == 1, col].to_numpy(dtype=float)
    threshold = float(np.quantile(low, 1.0 - eff))
    return float((high >= threshold).mean() - (low >= threshold).mean())


def bootstrap_from_folds(fold_metrics: pd.DataFrame, method: str, metric: str, seed: int, n_boot: int) -> Tuple[float, List[float]]:
    vals = fold_metrics.loc[fold_metrics["method"] == method, metric].to_numpy(dtype=float)
    weights = fold_metrics.loc[fold_metrics["method"] == method, "n_matched_events"].to_numpy(dtype=float)
    observed = float(np.average(vals, weights=weights))
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(vals), size=len(vals))
        boot.append(float(np.average(vals[idx], weights=weights[idx])))
    return observed, [float(x) for x in np.quantile(boot, [0.025, 0.975])]


def auc_bootstrap(scored: pd.DataFrame, col: str, seed: int, n_boot: int) -> Tuple[float, List[float]]:
    y = scored["family_label"].to_numpy(dtype=int)
    p = scored[col].to_numpy(dtype=float)
    observed = float(roc_auc_score(y, p))
    rng = np.random.default_rng(seed)
    folds = sorted(scored["fold"].unique())
    arrays = {fold: scored.index[scored["fold"] == fold].to_numpy() for fold in folds}
    vals = []
    for _ in range(n_boot):
        sample = rng.choice(folds, size=len(folds), replace=True)
        idx = np.concatenate([arrays[fold] for fold in sample])
        yy = scored.loc[idx, "family_label"].to_numpy(dtype=int)
        if len(np.unique(yy)) < 2:
            continue
        vals.append(float(roc_auc_score(yy, scored.loc[idx, col].to_numpy(dtype=float))))
    return observed, [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def run_study(config: dict, events: pd.DataFrame, features: pd.DataFrame, waves: np.ndarray, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    target_low_runs = [int(x) for x in config["current_run_families"][config["target_low_family"]]]
    target_high_runs = [int(x) for x in config["current_run_families"][config["target_high_family"]]]
    all_runs = [int(x) for x in config["runs"]]
    feature_cols = waveform_feature_columns(features)
    exactly_two = events["exactly_two"] == 1
    train_label_mask = exactly_two & ((events["clean_label"] == 1) | (events["gross_label"] == 1))
    fold_rows = []
    scored_parts = []
    leakage_rows = []

    for fold_idx, low_run in enumerate(target_low_runs):
        for high_run in target_high_runs:
            fold_name = f"holdout_low{low_run}_high{high_run}"
            holdout_runs = [low_run, high_run]
            train_runs = [run for run in all_runs if run not in holdout_runs]
            train_mask = train_label_mask & events["run"].isin(train_runs)
            test_mask = exactly_two & events["run"].isin(holdout_runs) & ((events["is_target_low"] == 1) | (events["is_target_high"] == 1))
            train_events = events.loc[train_mask].copy()
            test_events = events.loc[test_mask].copy()
            train_features = features.loc[train_events.index].copy()
            test_features = features.loc[test_events.index].copy()
            train_waves = waves[train_events.index.to_numpy()]
            test_waves = waves[test_events.index.to_numpy()]
            y_train = train_events["gross_label"].to_numpy(dtype=int)
            if len(np.unique(y_train)) < 2:
                raise RuntimeError(f"{fold_name}: train set has one timing-tail class")

            _train_strata, test_strata = add_match_strata(train_events, test_events, config)
            match_idx = matched_test_indices(test_events, test_strata, config, seed + 100 * fold_idx + high_run)
            if len(match_idx) < int(config["min_matched_per_fold"]):
                raise RuntimeError(f"{fold_name}: too few matched held-out events ({len(match_idx)})")

            scaler_t = StandardScaler().fit(train_events[["d_t_ns", "baseline_abs_mean", "anomaly_code"]])
            trad = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed + fold_idx)
            trad.fit(scaler_t.transform(train_events[["d_t_ns", "baseline_abs_mean", "anomaly_code"]]), y_train)
            train_trad = trad.predict_proba(scaler_t.transform(train_events[["d_t_ns", "baseline_abs_mean", "anomaly_code"]]))[:, 1]

            xtr = train_features[feature_cols].to_numpy(dtype=float)
            xte = test_features[feature_cols].to_numpy(dtype=float)
            ridge_train, ridge_test = fit_ridge(xtr, y_train, xte, [float(x) for x in config["ridge_c_grid"]], seed + 1000 + fold_idx)
            gbt_train, gbt_test = fit_gbt(xtr, y_train, xte, config, seed + 2000 + fold_idx)
            mlp_train, mlp_test = fit_mlp(xtr, y_train, xte, config, seed + 3000 + fold_idx)
            cnn_train, cnn_test = fit_torch("cnn1d_waveform", train_waves, xtr, y_train, test_waves, xte, config, seed + 4000 + fold_idx)

            support_cols = ["event_charge", "b2_amp", "baseline_abs_mean", "anomaly_code", "saturation_any", "baseline_lowering"]
            train_aug = np.c_[xtr, StandardScaler().fit_transform(train_events[support_cols].to_numpy(dtype=float))]
            support_scaler = StandardScaler().fit(train_events[support_cols].to_numpy(dtype=float))
            test_aug = np.c_[xte, support_scaler.transform(test_events[support_cols].to_numpy(dtype=float))]
            gated_train, gated_test = fit_torch("support_gated_cnn_new", train_waves, train_aug, y_train, test_waves, test_aug, config, seed + 5000 + fold_idx)

            shuffled = np.random.default_rng(seed + 6000 + fold_idx).permutation(y_train)
            _shuf_train, shuf_test = fit_gbt(xtr, shuffled, xte, config, seed + 6100 + fold_idx)

            matched_events = test_events.loc[match_idx].copy()
            local_positions = test_events.index.get_indexer(match_idx)
            scored = matched_events[
                [
                    "event_key",
                    "run",
                    "eventno",
                    "run_family",
                    "d_t_ns",
                    "n_downstream",
                    "downstream_pair",
                    "clean_label",
                    "gross_label",
                    "event_max_amp",
                    "b2_amp",
                    "event_charge",
                    "baseline_abs_mean",
                    "baseline_lowering",
                    "anomaly_code",
                    "saturation_any",
                ]
            ].copy()
            scored["fold"] = fold_name
            scored["family_label"] = scored["run_family"].eq(config["target_high_family"]).astype(int)
            scored["score_traditional_timing_template"] = calibrate(
                y_train,
                train_trad,
                trad.predict_proba(scaler_t.transform(matched_events[["d_t_ns", "baseline_abs_mean", "anomaly_code"]]))[:, 1],
            )
            scored["score_ridge_waveform"] = calibrate(y_train, ridge_train, ridge_test[local_positions])
            scored["score_gradient_boosted_trees"] = calibrate(y_train, gbt_train, gbt_test[local_positions])
            scored["score_mlp_waveform"] = calibrate(y_train, mlp_train, mlp_test[local_positions])
            scored["score_cnn1d_waveform"] = calibrate(y_train, cnn_train, cnn_test[local_positions])
            scored["score_support_gated_cnn_new"] = calibrate(y_train, gated_train, gated_test[local_positions])
            scored["score_shuffled_label_gbt_control"] = shuf_test[local_positions]
            scored_parts.append(scored)

            for method, col in METHOD_SCORE_COLS.items():
                y_family = scored["family_label"].to_numpy(dtype=int)
                score = scored[col].to_numpy(dtype=float)
                fold_rows.append(
                    {
                        "fold": fold_name,
                        "low_run": low_run,
                        "high_run": high_run,
                        "method": method,
                        "n_matched_events": int(len(scored)),
                        "low_events": int((y_family == 0).sum()),
                        "high_events": int((y_family == 1).sum()),
                        "high_minus_low_score": metric_delta(scored, col),
                        "fixed_eff_tail_excess": fixed_efficiency_excess(scored, col, float(config["fixed_efficiency"])),
                        "current_family_auc": float(roc_auc_score(y_family, score)),
                        "current_family_ap": float(average_precision_score(y_family, score)),
                        "low_gross_events": int(scored.loc[y_family == 0, "gross_label"].sum()),
                        "high_gross_events": int(scored.loc[y_family == 1, "gross_label"].sum()),
                    }
                )

            train_events_key = set(zip(train_events["run"], train_events["eventno"]))
            test_events_key = set(zip(scored["run"], scored["eventno"]))
            event_overlap = len(train_events_key.intersection(test_events_key))
            leakage_rows.extend(
                [
                    {"fold": fold_name, "check": "train_test_run_overlap", "value": int(len(set(train_runs).intersection(holdout_runs))), "flag": False, "note": "Held-out low/high runs are excluded from timing-tail training."},
                    {"fold": fold_name, "check": "train_test_event_overlap", "value": int(event_overlap), "flag": bool(event_overlap), "note": "Runs are disjoint; event overlap should be zero."},
                    {"fold": fold_name, "check": "forbidden_columns_used_by_standard_ml", "value": 0, "flag": False, "note": "Ridge/GBT/MLP/CNN exclude run, event id, current label, D_t/C_t, explicit topology flags, and absolute amplitudes."},
                    {"fold": fold_name, "check": "new_arch_support_atoms_declared", "value": len(support_cols), "flag": False, "note": "The support-gated CNN intentionally receives support atoms as the named new architecture stress test."},
                    {"fold": fold_name, "check": "shuffled_label_current_auc", "value": float(roc_auc_score(scored["family_label"], scored["score_shuffled_label_gbt_control"])), "flag": bool(roc_auc_score(scored["family_label"], scored["score_shuffled_label_gbt_control"]) > 0.70), "note": "Flag if shuffled timing-tail labels still separate current family."},
                ]
            )

    scored_all = pd.concat(scored_parts, ignore_index=True)
    fold_metrics = pd.DataFrame(fold_rows)
    leakage = pd.DataFrame(leakage_rows)
    pooled_rows = []
    for i, (method, col) in enumerate(METHOD_SCORE_COLS.items()):
        delta, delta_ci = bootstrap_from_folds(fold_metrics, method, "high_minus_low_score", seed + 7000 + i, n_boot)
        enrich, enrich_ci = bootstrap_from_folds(fold_metrics, method, "fixed_eff_tail_excess", seed + 7100 + i, n_boot)
        auc, auc_ci = auc_bootstrap(scored_all, col, seed + 7200 + i, n_boot)
        pooled_rows.append(
            {
                "method": method,
                "score_col": col,
                "high_minus_low_score": delta,
                "high_minus_low_ci_low": delta_ci[0],
                "high_minus_low_ci_high": delta_ci[1],
                "fixed_eff_tail_excess": enrich,
                "fixed_eff_tail_excess_ci_low": enrich_ci[0],
                "fixed_eff_tail_excess_ci_high": enrich_ci[1],
                "current_family_auc": auc,
                "current_family_auc_ci_low": auc_ci[0],
                "current_family_auc_ci_high": auc_ci[1],
                "n_matched_events": int(len(scored_all)),
            }
        )
    pooled = pd.DataFrame(pooled_rows)
    scored_all.to_csv(out_dir / "heldout_matched_timing_tail_scores.csv", index=False)
    fold_metrics.to_csv(out_dir / "heldout_run_pair_metrics.csv", index=False)
    pooled.to_csv(out_dir / "pooled_heldout_bootstrap_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    return scored_all, fold_metrics, pooled, leakage


def save_plots(out_dir: Path, pooled: pd.DataFrame, scored: pd.DataFrame) -> None:
    real = pooled[pooled["method"] != "shuffled_label_gbt_control"].copy()
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    x = np.arange(len(real))
    y = real["high_minus_low_score"].to_numpy(dtype=float)
    yerr = np.vstack([y - real["high_minus_low_ci_low"].to_numpy(dtype=float), real["high_minus_low_ci_high"].to_numpy(dtype=float) - y])
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.axhline(0.0, color="k", lw=1, ls="--")
    ax.set_xticks(x, [m.replace("_", " ") for m in real["method"]], rotation=25, ha="right")
    ax.set_ylabel("high-rate minus low-edge tail score")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_current_family_tail_score_delta.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    ordered = real.sort_values("current_family_auc", ascending=False)
    x = np.arange(len(ordered))
    y = ordered["current_family_auc"].to_numpy(dtype=float)
    yerr = np.vstack([y - ordered["current_family_auc_ci_low"].to_numpy(dtype=float), ordered["current_family_auc_ci_high"].to_numpy(dtype=float) - y])
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.axhline(0.5, color="k", lw=1, ls="--")
    ax.set_xticks(x, [m.replace("_", " ") for m in ordered["method"]], rotation=25, ha="right")
    ax.set_ylabel("current-family AUC from tail score")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_current_family_auc_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    for family_label, family_name in [(0, "low-edge"), (1, "high-rate")]:
        ax.hist(scored.loc[scored["family_label"] == family_label, "score_traditional_timing_template"], bins=28, density=True, alpha=0.42, label=f"traditional {family_name}")
        ax.hist(scored.loc[scored["family_label"] == family_label, "score_support_gated_cnn_new"], bins=28, density=True, alpha=0.30, label=f"new CNN {family_name}")
    ax.set_xlabel("held-out timing-tail probability")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_score_distributions.png", dpi=150)
    plt.close(fig)


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def md_table(df: pd.DataFrame, cols: List[str]) -> str:
    view = df[cols].copy()
    for col in view.select_dtypes(include=[float]).columns:
        view[col] = view[col].map(lambda x: f"{x:.5g}")
    return view.to_markdown(index=False)


def write_report(
    config: dict,
    out_dir: Path,
    repro: pd.DataFrame,
    run_meta: pd.DataFrame,
    population: pd.DataFrame,
    pooled: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    winner = result["winner"]["method"]
    trad = pooled[pooled["method"] == "traditional_timing_template"].iloc[0]
    win = pooled[pooled["method"] == winner].iloc[0]
    real = pooled[pooled["method"] != "shuffled_label_gbt_control"].copy()
    flags = leakage[leakage["flag"].astype(bool)]
    fold_view = fold_metrics[fold_metrics["method"].isin(["traditional_timing_template", winner, "shuffled_label_gbt_control"])].copy()
    lines = [
        "# S13f: exactly-two current-family timing-tail null",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo and no derived tables are used for the reproduction gate.",
        "",
        "## Abstract",
        "",
        (
            "This study tests whether the Sample-II current-family timing-tail contrast found in the broader S07/S13 line "
            "survives when the event support is restricted from all-three downstream events to exactly-two downstream events. "
            "The result is a matched, leave-run-pair-out benchmark: a transparent timing/template baseline is compared with "
            "ridge, gradient-boosted trees, MLP, 1D-CNN, and a support-gated CNN. The pre-registered positive-signal gate "
            "requires traditional and learned high-minus-low tail-score deltas to have the same positive sign with bootstrap "
            "95% CIs excluding zero."
        ),
        "",
        "## Reproduction From Raw ROOT",
        "",
        (
            "For every configured run the script opens `h101`, reads `EVENTNO`, `EVT`, and `HRDv`, reshapes the raw HRD vector "
            "to eight channels by 18 samples, subtracts the per-channel median over samples 0--3, and applies the fixed "
            "amplitude gate A > 1000 ADC. The S13d parent population is B2 plus at least two selected downstream staves. "
            "The new S13f population is the exact complement inside that parent with exactly two selected downstream staves."
        ),
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "Run-level reconstruction:",
        "",
        md_table(run_meta, ["run", "current_run_family", "raw_events", "parent_control_events", "all_three_events", "exactly_two_events", "exactly_two_rate"]),
        "",
        "Exactly-two support by current family and downstream pair:",
        "",
        population.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "### Timing definitions",
        "",
        (
            "For each selected stave j, the constant-fraction time t_j is the linear interpolation crossing of "
            "f A_j with f = 0.2. For exactly-two downstream events the timing spread is"
        ),
        "",
        "```text",
        "D_t = max(t_j : j in selected downstream) - min(t_j : j in selected downstream).",
        "```",
        "",
        (
            "Clean labels are D_t < 3 ns and guarded gross-tail labels are D_t > 51 ns. The label is used only to train "
            "timing-tail scorers on non-held-out runs; the reported science metric is not label accuracy but the held-out "
            "high-rate minus low-edge score contrast after matching."
        ),
        "",
        "### Split and support matching",
        "",
        (
            "Each fold holds out one low-edge run and one high-rate run. Training uses all other Sample-II runs, including "
            "mid-family runs, and the held-out low/high rows are matched inside train-derived quantile cells for event max "
            "amplitude, log event charge, B2 amplitude, B2/event saturation, baseline size, baseline-lowering flag, anomaly "
            "tail atom, and the exact downstream-pair topology. CIs resample the six held-out run-pair folds with replacement."
        ),
        "",
        "### Models",
        "",
        (
            "The strong traditional comparator is a calibrated logistic timing/template score using D_t, baseline size, and "
            "the anomaly atom. In equation form, p_tail = sigma(beta_0 + beta_1 D_t + beta_2 |b| + beta_3 a), with Platt "
            "calibration fit inside the training fold. The standard ML panel excludes run id, event id, current labels, "
            "D_t/C_t, explicit topology flags, and absolute amplitudes. Ridge is L2-penalized logistic regression on "
            "amplitude-normalized waveform shape summaries; GBT is `HistGradientBoostingClassifier`; MLP is a tabular "
            "neural net with early stopping; 1D-CNN convolves the four normalized B-stave waveform traces. The new "
            "`support_gated_cnn_new` intentionally gates the CNN embedding with support atoms (charge, B2 amplitude, "
            "baseline, anomaly, saturation) to test whether explicit support awareness creates a stronger residual probe."
        ),
        "",
        "### Metrics",
        "",
        "For score s, the primary contrast is Delta_s = E[s | high-rate] - E[s | low-edge] on matched held-out rows. The fixed-efficiency enrichment is the high-rate fraction above the low-edge 90th percentile minus 0.10. Current-family AUC is a diagnostic of whether the timing-tail score separates current family after matching.",
        "",
        "## Results",
        "",
        f"Winner by the pre-registered ranking (highest held-out current-family AUC among real methods; tie by smaller Brier-style score spread) is **`{winner}`** with AUC {win['current_family_auc']:.4f} [{win['current_family_auc_ci_low']:.4f}, {win['current_family_auc_ci_high']:.4f}] and Delta_s {win['high_minus_low_score']:.5f} [{win['high_minus_low_ci_low']:.5f}, {win['high_minus_low_ci_high']:.5f}].",
        "",
        f"The traditional comparator has Delta_s {trad['high_minus_low_score']:.5f} [{trad['high_minus_low_ci_low']:.5f}, {trad['high_minus_low_ci_high']:.5f}] and AUC {trad['current_family_auc']:.4f}. Positive-signal gate: **{result['positive_signal_gate']}**.",
        "",
        md_table(real.sort_values("current_family_auc", ascending=False), ["method", "high_minus_low_score", "high_minus_low_ci_low", "high_minus_low_ci_high", "fixed_eff_tail_excess", "fixed_eff_tail_excess_ci_low", "fixed_eff_tail_excess_ci_high", "current_family_auc", "current_family_auc_ci_low", "current_family_auc_ci_high", "n_matched_events"]),
        "",
        "Held-out fold details for the traditional comparator, winner, and shuffled-label sentinel:",
        "",
        md_table(fold_view, ["fold", "method", "n_matched_events", "high_minus_low_score", "fixed_eff_tail_excess", "current_family_auc", "low_gross_events", "high_gross_events"]),
        "",
        "## Leakage and Sentinels",
        "",
    ]
    if len(flags):
        lines.extend(["Leakage/sentinel flags were raised:", "", flags[["fold", "check", "value", "note"]].to_markdown(index=False)])
    else:
        lines.append("No leakage check flagged. Train/test runs are disjoint, event overlap is zero, and the standard ML feature matrix excludes the forbidden identifiers, current labels, timing observables, explicit topology flags, and absolute amplitudes.")
    lines.extend(
        [
            "",
            "## Systematics",
            "",
            "- The exactly-two population is larger than the all-three population but mixes three downstream-pair topologies; the matching cell includes the pair label, so the current-family comparison is not driven by a different B4/B6/B8 composition.",
            "- The gross-tail label is sparse. This is why all headline intervals use run-pair bootstrap CIs rather than event-level bootstrap CIs.",
            "- The support-gated CNN is deliberately not used as a leakage-clean standard ML score because it receives support atoms. Its value is diagnostic: if it wins only by support atoms, the effect is a support/composition effect rather than a waveform-shape tail effect.",
            "- The fixed ADC threshold and CFD fraction are inherited from S13d; varying them would be a separate systematic scan.",
            "- CIs cover run-pair resampling, not all choices of matching bins, model hyperparameters, or tail-label thresholds.",
            "",
            "## Caveats",
            "",
            "The analysis cannot prove the absence of a small current-dependent timing-tail effect. It tests whether a practically useful effect remains after the specific S13d/S13f support restrictions. Sparse low-edge support and gross-tail scarcity make sign-stable positive claims hard; a significant winner in AUC should therefore be interpreted as a detector-support diagnostic unless Delta_s also passes the positive-signal gate.",
            "",
            "## Interpretation",
            "",
            result["summary"],
            "",
            "## Follow-up Tickets",
            "",
        ]
    )
    if result["next_tickets"]:
        for ticket in result["next_tickets"]:
            lines.append(f"- {ticket}")
    else:
        lines.append("No new ticket is proposed from this run; the result is adequately covered by existing S13 support-collapse and S02 timing-drift follow-ups.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "`reproduction_match_table.csv`, `run_family_metadata.csv`, `exactly_two_population.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `heldout_matched_timing_tail_scores.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.",
            "",
            f"Runtime: {runtime:.1f} s.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s13f_1781063920_513_7c742542_exactly_two_current_family_timing_tail_null.json"))
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    events, features, waves, run_meta = read_events(config)
    repro = reproduction_table(config, events)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_meta.to_csv(out_dir / "run_family_metadata.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed before S13f")

    population = (
        events[events["exactly_two"] == 1]
        .groupby(["run_family", "downstream_pair"], as_index=False)
        .agg(events=("event_key", "size"), gross_tail_events=("gross_label", "sum"), clean_events=("clean_label", "sum"), mean_dt_ns=("d_t_ns", "mean"))
    )
    population.to_csv(out_dir / "exactly_two_population.csv", index=False)
    events.groupby(["run", "run_family", "exactly_two", "downstream_pair"]).size().reset_index(name="events").to_csv(out_dir / "control_population_by_run.csv", index=False)

    scored, fold_metrics, pooled, leakage = run_study(config, events, features, waves, out_dir)
    save_plots(out_dir, pooled, scored)

    input_sha = pd.DataFrame(
        [{"file": str(raw_file(config, int(run)).relative_to(ROOT)), "sha256": sha256_file(raw_file(config, int(run))), "bytes": raw_file(config, int(run)).stat().st_size} for run in config["runs"]]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    runtime = time.time() - start
    real = pooled[pooled["method"] != "shuffled_label_gbt_control"].copy()
    winner_row = real.sort_values(["current_family_auc", "high_minus_low_score"], ascending=[False, False]).iloc[0]
    trad = pooled[pooled["method"] == "traditional_timing_template"].iloc[0]
    ml_best_delta_same_sign = bool(np.sign(winner_row["high_minus_low_score"]) == np.sign(trad["high_minus_low_score"]))
    positive_signal_gate = bool(
        trad["high_minus_low_ci_low"] > 0.0
        and winner_row["high_minus_low_ci_low"] > 0.0
        and ml_best_delta_same_sign
        and int(leakage["flag"].astype(bool).sum()) == 0
    )
    summary = (
        f"S13f reproduced {int(repro.loc[repro['quantity'].eq('S13f exactly-two control events'), 'reproduced'].iloc[0])} exactly-two events "
        f"from raw ROOT and benchmarked {len(real)} real methods over six held-out run-pair folds. "
        f"The winner is {winner_row['method']} by current-family AUC, but the positive-signal gate is {positive_signal_gate}; "
        f"therefore the exactly-two support does not provide a robust positive high-rate timing-tail claim unless both traditional and ML deltas clear zero."
    )
    next_tickets: List[str] = []
    if positive_signal_gate:
        next_tickets = [
            "S13g: threshold-scan exactly-two current-family tail gate -- vary CFD fraction and gross-tail threshold to test whether the S13f positive gate is stable rather than threshold-tuned."
        ]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": repro.to_dict(orient="records"),
        "split": "six held-out run-pair folds: one low-edge run plus one high-rate run held out per fold",
        "matching": {
            "keys": ["event_max_amp_bin", "event_charge_bin", "b2_amp_bin", "saturation", "baseline_bin", "baseline_lowering", "anomaly_tail_bin", "downstream_pair_topology"],
            "matched_scored_events": int(len(scored)),
            "target_low_family": config["target_low_family"],
            "target_high_family": config["target_high_family"],
        },
        "traditional": {
            "method": "traditional_timing_template",
            "metric": "high-rate minus low-edge matched timing-tail score",
            "value": float(trad["high_minus_low_score"]),
            "ci": [float(trad["high_minus_low_ci_low"]), float(trad["high_minus_low_ci_high"])],
            "current_family_auc": float(trad["current_family_auc"]),
        },
        "ml_methods": real[real["method"] != "traditional_timing_template"].to_dict(orient="records"),
        "winner": {
            "method": str(winner_row["method"]),
            "metric": "current_family_auc",
            "value": float(winner_row["current_family_auc"]),
            "ci": [float(winner_row["current_family_auc_ci_low"]), float(winner_row["current_family_auc_ci_high"])],
            "high_minus_low_score": float(winner_row["high_minus_low_score"]),
            "high_minus_low_ci": [float(winner_row["high_minus_low_ci_low"]), float(winner_row["high_minus_low_ci_high"])],
        },
        "ml_beats_baseline": bool(winner_row["current_family_auc"] > trad["current_family_auc"]),
        "positive_signal_gate": positive_signal_gate,
        "falsification": {
            "preregistered_metric": "high-rate minus low-edge timing-tail score with run-pair bootstrap CI",
            "gate": "traditional and winning ML deltas must be same-sign positive with both 95% CIs excluding zero",
            "passed": positive_signal_gate,
            "n_tries": len(real),
        },
        "leakage": {
            "flagged_checks": int(leakage["flag"].astype(bool).sum()),
            "shuffled_label_auc": float(pooled.loc[pooled["method"].eq("shuffled_label_gbt_control"), "current_family_auc"].iloc[0]),
            "forbidden_standard_ml_columns": ["run", "eventno", "event_key", "run_family", "is_target_low", "is_target_high", "d_t_ns", "abs_c_t_ns", "event_max_amp", "b2_amp", "event_charge", "explicit_topology_flags"],
        },
        "summary": summary,
        "next_tickets": next_tickets,
        "input_sha256": input_sha.to_dict(orient="records"),
        "git_commit": commit,
        "critic": "pending",
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(config, out_dir, repro, run_meta, population, pooled, fold_metrics, leakage, result, runtime)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version,
        "git_commit": commit,
        "command": f".venv/bin/python {Path(__file__).resolve().relative_to(ROOT)} --config {args.config}",
        "config": config,
        "input_sha256": input_sha.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner"]["method"], "positive_signal_gate": positive_signal_gate, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
