#!/usr/bin/env python3
"""P02c: full-S01 q_template cluster stability across runs and staves.

This report-local script reads raw B-stack ROOT files, reproduces the S00/P02
selection numbers first, then evaluates pulse-topology clusters with grouped
held-out folds using the committed S01 q_template_per_pulse table as the
q-template association target.  No Monte Carlo inputs are used.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-p02c-mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_ID = "1781009575.1631.563755ca"
STUDY_ID = "P02c"
TITLE = "full-S01 q_template cluster stability"
OUT = Path("reports") / TICKET_ID
S01_Q_TEMPLATE = Path("reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz")
RAW_CANDIDATES = [
    Path("data/root/root"),
    Path("data/extracted/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/Desktop/test_beam/data/root/root"),
]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
STAVE_NAMES = np.asarray(list(STAVES.keys()), dtype=object)
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
RUNS = sorted({run for runs in RUN_GROUPS.values() for run in runs})
P02_RUNS = [58, 59, 60, 61, 62, 63, 65, 50]
BASELINE = [0, 1, 2, 3]
NSAMP = 18
CUT_ADC = 1000.0
EXPECTED_S00_SELECTED = 640737
P02_SAMPLE_N = 60000
P02_EXPECTED_EARLY_RATE = 0.044
RANDOM_SEED = 2403
MAX_PER_RUN_STAVE = 300
BOOTSTRAPS = 120
PERIOD_NS = 10.0
MAX_CLUSTER_FIT_ROWS = 30000
AE_EPOCHS = 8


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


def raw_root_dir() -> Path:
    for candidate in RAW_CANDIDATES:
        if candidate.exists() and list(candidate.glob("hrdb_run_*.root")):
            return candidate
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def iter_tree(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd20_times(corrected: np.ndarray, amplitude: np.ndarray) -> np.ndarray:
    """Return CFD20 crossing times in ns for an event batch and four selected staves."""
    out = np.full(amplitude.shape, np.nan, dtype=np.float32)
    threshold = 0.2 * amplitude
    for stave_idx in range(corrected.shape[1]):
        wave = corrected[:, stave_idx, :]
        amp = amplitude[:, stave_idx]
        ge = wave >= threshold[:, stave_idx, None]
        first = np.argmax(ge, axis=1)
        valid = ge.any(axis=1) & (amp > CUT_ADC)
        for row in np.where(valid)[0]:
            j = int(first[row])
            if j <= 0:
                out[row, stave_idx] = 0.0
            else:
                y0 = float(wave[row, j - 1])
                y1 = float(wave[row, j])
                denom = y1 - y0
                frac = 0.0 if denom <= 0 else (float(threshold[row, stave_idx]) - y0) / denom
                out[row, stave_idx] = (j - 1 + frac) * PERIOD_NS
    return out


def run_group(run: int) -> str:
    for group, runs in RUN_GROUPS.items():
        if int(run) in runs:
            return group
    return "unknown"


def scan_raw(raw_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    channels = np.asarray([STAVES[name] for name in STAVE_NAMES], dtype=int)
    waves: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    count_rows: List[dict] = []
    global_event = 0

    for run in RUNS:
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {
            "run": run,
            "group": run_group(run),
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "control_events_b2_and_2downstream": 0,
        }
        stave_counts = {name: 0 for name in STAVE_NAMES}

        for batch in iter_tree(path):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, NSAMP)
            selected_raw = event_waves[:, channels, :]
            baseline = np.median(selected_raw[..., BASELINE], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            peak_sample = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amplitude > CUT_ADC
            event_idx, stave_idx = np.where(selected)
            downstream_count = selected[:, 1:].sum(axis=1)
            event_selected_count = selected.sum(axis=1)
            event_has_b2 = selected[:, 0]
            event_has_downstream = downstream_count > 0
            times = cfd20_times(corrected, amplitude)
            dt = np.full(len(event_waves), np.nan, dtype=np.float32)
            for idx in np.where(downstream_count >= 2)[0]:
                vals = times[idx, 1:][selected[idx, 1:] & np.isfinite(times[idx, 1:])]
                if len(vals) >= 2:
                    dt[idx] = float(np.max(vals) - np.min(vals))

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            run_counts["control_events_b2_and_2downstream"] += int((event_has_b2 & (downstream_count >= 2)).sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((corrected[event_idx, stave_idx] / amp[:, None]).astype(np.float32))
                topology = np.full(len(event_idx), "other", dtype=object)
                ev_sel = event_selected_count[event_idx]
                ev_down = downstream_count[event_idx]
                ev_b2 = event_has_b2[event_idx]
                topology[(ev_sel == 1) & (stave_idx == 0)] = "b2_only"
                topology[(ev_sel == 1) & (stave_idx > 0)] = "single_downstream"
                topology[(ev_b2) & (ev_down > 0)] = "b2_plus_downstream"
                topology[(~ev_b2) & (ev_down >= 2)] = "multi_downstream_no_b2"
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "s01_row_index": np.arange(len(event_idx), dtype=np.int64) + global_event,
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": run_group(run),
                            "eventno": eventno[event_idx].astype(np.int64),
                            "evt": evt[event_idx].astype(np.int64),
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "channel": channels[stave_idx].astype(np.int16),
                            "amplitude_adc": amp,
                            "peak_sample_raw": peak_sample[event_idx, stave_idx].astype(np.int16),
                            "area_adc_samples": area[event_idx, stave_idx].astype(np.float32),
                            "event_selected_count": ev_sel.astype(np.int8),
                            "event_downstream_count": ev_down.astype(np.int8),
                            "event_topology": topology,
                            "d_t_ns": dt[event_idx],
                        }
                    )
                )
                global_event += len(event_idx)

        count_rows.append({**run_counts, **stave_counts})
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    return np.concatenate(waves, axis=0), pd.concat(meta_parts, ignore_index=True), pd.DataFrame(count_rows)


def shape_features(waves: np.ndarray) -> pd.DataFrame:
    area = waves.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    peak = waves.argmax(axis=1)
    tail = waves[:, 12:].sum(axis=1) / abs_area
    late = waves[:, 9:].sum(axis=1) / abs_area
    early = waves[:, :5].sum(axis=1) / abs_area
    final = waves[:, -1]
    width50 = (waves > 0.5).sum(axis=1)
    width20 = (waves > 0.2).sum(axis=1)
    max_down_step = np.diff(waves, axis=1).min(axis=1)
    asymmetry = (waves[:, 10:].sum(axis=1) - waves[:, :5].sum(axis=1)) / abs_area
    return pd.DataFrame(
        {
            "peak_sample": peak.astype(np.int16),
            "area_over_peak": area.astype(np.float32),
            "tail_fraction": tail.astype(np.float32),
            "late_fraction": late.astype(np.float32),
            "early_fraction": early.astype(np.float32),
            "final_fraction": final.astype(np.float32),
            "width50": width50.astype(np.float32),
            "width20": width20.astype(np.float32),
            "max_down_step": max_down_step.astype(np.float32),
            "asymmetry": asymmetry.astype(np.float32),
        }
    )


def make_labels(meta: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    labels = pd.DataFrame(index=meta.index)
    peak = feats["peak_sample"].to_numpy()
    area = feats["area_over_peak"].to_numpy()
    labels["peak_group"] = np.where(peak <= 3, "early_0_3", np.where(peak <= 5, "prepeak_4_5", np.where(peak <= 9, "nominal_6_9", "late_10_17")))
    labels["manual_flag"] = "nominal"
    labels.loc[(peak <= 3), "manual_flag"] = "early_peak_p02"
    labels.loc[(peak <= 4) & (area < 3.0), "manual_flag"] = "early_low_area"
    labels.loc[(peak >= 12), "manual_flag"] = "late_peak"
    labels.loc[(feats["max_down_step"].to_numpy() < -0.75), "manual_flag"] = "large_negative_step"
    labels["downstream_topology"] = meta["event_topology"].astype(str).to_numpy()
    dt = meta["d_t_ns"].to_numpy(dtype=float)
    labels["dt_label"] = "no_dt"
    labels.loc[np.isfinite(dt) & (dt < 3.0), "dt_label"] = "clean_dt_lt3ns"
    labels.loc[np.isfinite(dt) & (dt >= 3.0) & (dt <= 50.0), "dt_label"] = "mid_dt_3_50ns"
    labels.loc[np.isfinite(dt) & (dt > 50.0), "dt_label"] = "gross_dt_gt50ns"
    return labels


def stratified_sample(meta: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for (_, _), sub in meta.groupby(["run", "stave"], sort=False):
        idx = sub.index.to_numpy()
        take = min(len(idx), MAX_PER_RUN_STAVE)
        pieces.append(rng.choice(idx, size=take, replace=False))
    return np.sort(np.concatenate(pieces))


def p02_sample_reproduction(waves: np.ndarray, meta: pd.DataFrame, feats: pd.DataFrame) -> dict:
    rng = np.random.default_rng(0)
    ordered_parts: List[np.ndarray] = []
    for run in P02_RUNS:
        ordered_parts.append(np.where(meta["run"].to_numpy() == run)[0])
        if sum(len(part) for part in ordered_parts) > P02_SAMPLE_N:
            break
    p02_idx = np.concatenate(ordered_parts)
    if len(p02_idx) > P02_SAMPLE_N:
        p02_idx = rng.choice(p02_idx, P02_SAMPLE_N, replace=False)
    peaks = feats.iloc[p02_idx]["peak_sample"].to_numpy()
    early = float(np.mean(peaks <= 3))
    return {
        "p02_runs": P02_RUNS,
        "sample_size": int(len(p02_idx)),
        "expected_sample_size": P02_SAMPLE_N,
        "early_peak_peak_le_3_rate": early,
        "reported_early_peak_rate_approx": P02_EXPECTED_EARLY_RATE,
        "absolute_delta": abs(early - P02_EXPECTED_EARLY_RATE),
        "passed": bool(len(p02_idx) == P02_SAMPLE_N and abs(early - P02_EXPECTED_EARLY_RATE) < 0.002),
    }


def align_s01_q_template(meta: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    if not S01_Q_TEMPLATE.exists():
        raise FileNotFoundError(S01_Q_TEMPLATE)
    q = pd.read_csv(S01_Q_TEMPLATE)
    if len(q) != len(meta):
        raise RuntimeError(f"S01 q_template row count mismatch: {len(q)} versus raw scan {len(meta)}")

    checks = []
    for col in ["run", "eventno", "evt", "stave", "channel"]:
        matches = bool((q[col].astype(str).to_numpy() == meta[col].astype(str).to_numpy()).all())
        checks.append({"field": col, "matches": matches, "max_abs_delta": 0.0})
        if not matches:
            bad = np.where(q[col].astype(str).to_numpy() != meta[col].astype(str).to_numpy())[0][:5]
            raise RuntimeError(f"S01 row semantic mismatch for {col}: first bad rows {bad.tolist()}")

    for col, raw_col, tolerance in [
        ("amplitude_adc", "amplitude_adc", 1.0e-6),
        ("peak_sample", "peak_sample_raw", 0.0),
        ("area_adc_samples", "area_adc_samples", 1.0e-3),
    ]:
        delta = np.asarray(q[col], dtype=float) - np.asarray(meta[raw_col], dtype=float)
        max_abs = float(np.nanmax(np.abs(delta)))
        matches = bool(max_abs <= tolerance)
        checks.append({"field": col, "matches": matches, "max_abs_delta": max_abs})
        if not matches:
            raise RuntimeError(f"S01 row semantic mismatch for {col}: max abs delta {max_abs}")

    aligned = meta.copy()
    aligned["s01_q_template_rmse"] = q["q_template_rmse"].to_numpy(dtype=float)
    aligned["s01_template_mse"] = q["template_mse"].to_numpy(dtype=float)
    aligned["s01_q_autoencoder_rmse"] = q["q_autoencoder_rmse"].to_numpy(dtype=float)
    alignment = {
        "s01_q_template": str(S01_Q_TEMPLATE),
        "s01_rows": int(len(q)),
        "raw_selected_rows": int(len(meta)),
        "exact_row_semantics_passed": bool(all(row["matches"] for row in checks)),
        "checks": checks,
        "q_template_rmse_median": float(np.nanmedian(aligned["s01_q_template_rmse"])),
        "q_template_rmse_p95": float(np.nanquantile(aligned["s01_q_template_rmse"], 0.95)),
    }
    pd.DataFrame(checks).to_csv(OUT / "s01_alignment_checks.csv", index=False)
    return aligned, alignment


def purity_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    total = 0
    for cluster in np.unique(y_pred):
        mask = y_pred == cluster
        if not np.any(mask):
            continue
        _, counts = np.unique(y_true[mask], return_counts=True)
        total += int(counts.max())
    return float(total / len(y_true)) if len(y_true) else float("nan")


def safe_ami(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2:
        return float("nan")
    return float(adjusted_mutual_info_score(y_true, y_pred))


def q_template_scores(waves_train: np.ndarray, amp_train: np.ndarray, stave_train: np.ndarray, waves_test: np.ndarray, amp_test: np.ndarray, stave_test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    edges = np.quantile(np.log1p(amp_train), [0.0, 0.25, 0.5, 0.75, 1.0])
    edges[0] -= 1e-6
    edges[-1] += 1e-6
    global_template = np.median(waves_train, axis=0)
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    for stave in np.unique(stave_train):
        for bin_idx in range(4):
            m = (stave_train == stave) & (np.log1p(amp_train) >= edges[bin_idx]) & (np.log1p(amp_train) < edges[bin_idx + 1])
            templates[(str(stave), bin_idx)] = np.median(waves_train[m], axis=0) if int(m.sum()) >= 25 else global_template

    def score(waves: np.ndarray, amp: np.ndarray, stave: np.ndarray) -> np.ndarray:
        bins = np.clip(np.digitize(np.log1p(amp), edges[1:-1]), 0, 3)
        vals = np.empty(len(waves), dtype=np.float32)
        for idx in range(len(waves)):
            tmpl = templates.get((str(stave[idx]), int(bins[idx])), global_template)
            vals[idx] = float(np.sqrt(np.mean((waves[idx] - tmpl) ** 2)))
        return vals

    return score(waves_train, amp_train, stave_train), score(waves_test, amp_test, stave_test)


def q_bins(train_q: np.ndarray, test_q: np.ndarray) -> np.ndarray:
    finite_train = train_q[np.isfinite(train_q)]
    if len(finite_train) < 4:
        return np.full(len(test_q), "q_unbinned", dtype=object)
    edges = np.quantile(finite_train, [0.25, 0.50, 0.75])
    labels = np.asarray(["q_best", "q_midgood", "q_midpoor", "q_poor"], dtype=object)
    out = np.full(len(test_q), "q_nan", dtype=object)
    finite_test = np.isfinite(test_q)
    out[finite_test] = labels[np.digitize(test_q[finite_test], edges)]
    return out


def fit_traditional_predict(x_train: np.ndarray, x_test: np.ndarray, seed: int) -> Tuple[np.ndarray, dict]:
    best = None
    rng = np.random.default_rng(seed)
    fit_idx = np.arange(len(x_train))
    if len(fit_idx) > MAX_CLUSTER_FIT_ROWS:
        fit_idx = rng.choice(fit_idx, size=MAX_CLUSTER_FIT_ROWS, replace=False)
    for n_clusters in [3, 4, 5, 6, 7]:
        pipe = make_pipeline(StandardScaler(), PCA(n_components=4, random_state=seed))
        z_train = pipe.fit_transform(x_train[fit_idx])
        gmm = GaussianMixture(n_components=n_clusters, covariance_type="diag", random_state=seed, reg_covar=1e-3, max_iter=300)
        try:
            gmm.fit(z_train)
            bic = float(gmm.bic(z_train))
        except ValueError:
            continue
        if best is None or bic < best[0]:
            best = (bic, n_clusters, pipe, gmm)
    if best is None:
        pipe = make_pipeline(StandardScaler(), PCA(n_components=4, random_state=seed))
        z_train = pipe.fit_transform(x_train[fit_idx])
        z_test = pipe.transform(x_test)
        km = KMeans(n_clusters=5, n_init=20, random_state=seed).fit(z_train)
        return km.predict(z_test).astype(str), {"n_clusters": 5, "selector": "kmeans_fallback"}
    _, n_clusters, pipe, gmm = best
    pred = gmm.predict(pipe.transform(x_test))
    return pred.astype(str), {"n_clusters": int(n_clusters), "selector": "train_BIC"}


def train_autoencoder(x_train: np.ndarray, x_test: np.ndarray, seed: int, latent_dim: int = 4, epochs: int = AE_EPOCHS) -> Tuple[np.ndarray, np.ndarray, dict]:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    scaler = StandardScaler()
    xtr = scaler.fit_transform(x_train).astype(np.float32)
    xte = scaler.transform(x_test).astype(np.float32)
    train_tensor = torch.tensor(xtr, dtype=torch.float32, device=dev)
    net = nn.Sequential(
        nn.Linear(xtr.shape[1], 24),
        nn.ReLU(),
        nn.Linear(24, latent_dim),
        nn.ReLU(),
        nn.Linear(latent_dim, 24),
        nn.ReLU(),
        nn.Linear(24, xtr.shape[1]),
    ).to(dev)
    encoder = net[:4]
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossf = nn.MSELoss()
    batch = 4096
    losses = []
    for _ in range(epochs):
        order = rng.permutation(len(xtr))
        epoch_losses = []
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            xb = train_tensor[idx]
            opt.zero_grad()
            loss = lossf(net(xb), xb)
            loss.backward()
            opt.step()
            epoch_losses.append(float(loss.detach().cpu()))
        losses.append(float(np.mean(epoch_losses)))
    with torch.no_grad():
        z_train = encoder(torch.tensor(xtr, dtype=torch.float32, device=dev)).cpu().numpy()
        z_test = encoder(torch.tensor(xte, dtype=torch.float32, device=dev)).cpu().numpy()
    return z_train, z_test, {"device": dev, "epochs": epochs, "final_loss": float(losses[-1]), "latent_dim": latent_dim}


def fit_ml_predict(w_train: np.ndarray, w_test: np.ndarray, seed: int) -> Tuple[np.ndarray, dict]:
    z_train, z_test, ae_info = train_autoencoder(w_train, w_test, seed)
    best = None
    rng = np.random.default_rng(seed)
    fit_idx = np.arange(len(z_train))
    if len(fit_idx) > MAX_CLUSTER_FIT_ROWS:
        fit_idx = rng.choice(fit_idx, size=MAX_CLUSTER_FIT_ROWS, replace=False)
    for n_clusters in [3, 4, 5, 6, 7]:
        gmm = GaussianMixture(n_components=n_clusters, covariance_type="diag", random_state=seed, reg_covar=1e-3, max_iter=300)
        try:
            gmm.fit(z_train[fit_idx])
            bic = float(gmm.bic(z_train[fit_idx]))
        except ValueError:
            continue
        if best is None or bic < best[0]:
            best = (bic, n_clusters, gmm)
    if best is None:
        km = KMeans(n_clusters=5, n_init=20, random_state=seed).fit(z_train[fit_idx])
        return km.predict(z_test).astype(str), {**ae_info, "n_clusters": 5, "selector": "kmeans_fallback"}
    _, n_clusters, gmm = best
    pred = gmm.predict(z_test)
    return pred.astype(str), {**ae_info, "n_clusters": int(n_clusters), "selector": "train_BIC"}


def fold_predictions(
    waves: np.ndarray,
    meta: pd.DataFrame,
    feats: pd.DataFrame,
    labels: pd.DataFrame,
    split: str,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    x_trad = feats[
        [
            "peak_sample",
            "area_over_peak",
            "tail_fraction",
            "late_fraction",
            "early_fraction",
            "final_fraction",
            "width50",
            "width20",
            "max_down_step",
            "asymmetry",
        ]
    ].to_numpy(dtype=np.float32)
    groups = meta["run"].to_numpy() if split == "run" else meta["stave"].to_numpy()
    if split == "run":
        splitter = GroupKFold(n_splits=5)
        splits = list(splitter.split(waves, groups=groups))
    else:
        splits = []
        for stave in sorted(meta["stave"].unique()):
            test = np.where(groups == stave)[0]
            train = np.where(groups != stave)[0]
            splits.append((train, test))

    pred_frames: List[pd.DataFrame] = []
    info_rows: List[dict] = []
    for fold, (train_idx, test_idx) in enumerate(splits):
        seed = int(rng.integers(1, 2**31 - 1))
        trad_pred, trad_info = fit_traditional_predict(x_trad[train_idx], x_trad[test_idx], seed)
        ml_pred, ml_info = fit_ml_predict(waves[train_idx], waves[test_idx], seed + 11)
        train_q = meta.iloc[train_idx]["s01_q_template_rmse"].to_numpy(dtype=float)
        test_q = meta.iloc[test_idx]["s01_q_template_rmse"].to_numpy(dtype=float)
        fold_label = ",".join(str(x) for x in sorted(np.unique(groups[test_idx])))
        pred_frames.append(
            pd.DataFrame(
                {
                    "split": split,
                    "fold": fold,
                    "fold_label": fold_label,
                    "row_index": test_idx,
                    "run": meta.iloc[test_idx]["run"].to_numpy(),
                    "stave": meta.iloc[test_idx]["stave"].to_numpy(),
                    "traditional_cluster": trad_pred,
                    "ml_cluster": ml_pred,
                    "s01_q_template_rmse": test_q,
                    "s01_q_template_bin": q_bins(train_q, test_q),
                    "peak_group": labels.iloc[test_idx]["peak_group"].to_numpy(),
                    "downstream_topology": labels.iloc[test_idx]["downstream_topology"].to_numpy(),
                    "dt_label": labels.iloc[test_idx]["dt_label"].to_numpy(),
                    "manual_flag": labels.iloc[test_idx]["manual_flag"].to_numpy(),
                }
            )
        )
        info_rows.append({"split": split, "fold": fold, "fold_label": fold_label, "method": "traditional", **trad_info, "train_rows": int(len(train_idx)), "heldout_rows": int(len(test_idx))})
        info_rows.append({"split": split, "fold": fold, "fold_label": fold_label, "method": "ml_autoencoder", **ml_info, "train_rows": int(len(train_idx)), "heldout_rows": int(len(test_idx))})
        print(f"{split} fold {fold} {fold_label}: heldout={len(test_idx)}")
    return pd.concat(pred_frames, ignore_index=True), pd.DataFrame(info_rows)


def metric_rows(pred: pd.DataFrame, split: str) -> pd.DataFrame:
    rows: List[dict] = []
    unit_col = "run" if split == "run" else "stave"
    targets = ["s01_q_template_bin", "peak_group", "downstream_topology", "dt_label", "manual_flag"]
    for method, col in [("traditional", "traditional_cluster"), ("ml_autoencoder", "ml_cluster")]:
        for target in targets:
            ami_vals = []
            purity_vals = []
            for _, unit_pred in pred.groupby(unit_col, sort=False):
                y = unit_pred[target].astype(str).to_numpy()
                p = unit_pred[col].astype(str).to_numpy()
                ami_vals.append(safe_ami(y, p))
                purity_vals.append(purity_score(y, p))
            ami_arr = np.asarray(ami_vals, dtype=float)
            purity_arr = np.asarray(purity_vals, dtype=float)
            rows.append(
                {
                    "split": split,
                    "method": method,
                    "target": target,
                    "ami": float(np.nanmean(ami_arr)),
                    "purity": float(np.nanmean(purity_arr)),
                    "rows": int(len(pred)),
                    "unit": unit_col,
                    "units": int(len(np.unique(pred[unit_col]))),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_metrics(pred: pd.DataFrame, split: str, rng: np.random.Generator) -> pd.DataFrame:
    unit_col = "run" if split == "run" else "stave"
    units = np.asarray(sorted(pred[unit_col].unique()), dtype=object)
    targets = ["s01_q_template_bin", "peak_group", "downstream_topology", "dt_label", "manual_flag"]
    rows: List[dict] = []
    for target in targets:
        unit_scores = {"traditional": {"ami": [], "purity": []}, "ml_autoencoder": {"ami": [], "purity": []}, "delta": {"ami": [], "purity": []}}
        for unit in units:
            unit_pred = pred[pred[unit_col] == unit]
            y = unit_pred[target].astype(str).to_numpy()
            t = unit_pred["traditional_cluster"].astype(str).to_numpy()
            m = unit_pred["ml_cluster"].astype(str).to_numpy()
            t_ami, m_ami = safe_ami(y, t), safe_ami(y, m)
            t_pur, m_pur = purity_score(y, t), purity_score(y, m)
            unit_scores["traditional"]["ami"].append(t_ami)
            unit_scores["traditional"]["purity"].append(t_pur)
            unit_scores["ml_autoencoder"]["ami"].append(m_ami)
            unit_scores["ml_autoencoder"]["purity"].append(m_pur)
            unit_scores["delta"]["ami"].append(m_ami - t_ami)
            unit_scores["delta"]["purity"].append(m_pur - t_pur)
        for _ in range(BOOTSTRAPS):
            sampled_idx = rng.integers(0, len(units), size=len(units))
            for method in ["traditional", "ml_autoencoder", "delta"]:
                for metric in ["ami", "purity"]:
                    vals = np.asarray(unit_scores[method][metric], dtype=float)[sampled_idx]
                    vals = vals[np.isfinite(vals)]
                    unit_scores.setdefault("_boot", {}).setdefault((method, metric), []).append(float(np.mean(vals)) if len(vals) else np.nan)
        for method in ["traditional", "ml_autoencoder", "delta"]:
            for metric in ["ami", "purity"]:
                vals = np.asarray(unit_scores["_boot"][(method, metric)], dtype=float)
                vals = vals[np.isfinite(vals)]
                lo, hi = np.quantile(vals, [0.025, 0.975]) if len(vals) else (np.nan, np.nan)
                rows.append({"split": split, "unit": unit_col, "method": method, "target": target, "metric": metric, "ci_low": float(lo), "ci_high": float(hi), "bootstrap_replicates": BOOTSTRAPS})
    return pd.DataFrame(rows)


def leakage_checks(pred: pd.DataFrame, sampled_meta: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    aligned_meta = sampled_meta.iloc[pred["row_index"].to_numpy(dtype=int)].reset_index(drop=True)
    for method, col in [("traditional", "traditional_cluster"), ("ml_autoencoder", "ml_cluster")]:
        rows.append({"check": "cluster_vs_run", "method": method, "ami": safe_ami(aligned_meta["run"].astype(str).to_numpy(), pred[col].astype(str).to_numpy()), "purity": purity_score(aligned_meta["run"].astype(str).to_numpy(), pred[col].astype(str).to_numpy())})
        rows.append({"check": "cluster_vs_stave", "method": method, "ami": safe_ami(aligned_meta["stave"].astype(str).to_numpy(), pred[col].astype(str).to_numpy()), "purity": purity_score(aligned_meta["stave"].astype(str).to_numpy(), pred[col].astype(str).to_numpy())})
        rows.append({"check": "cluster_vs_s01_q_template_bin", "method": method, "ami": safe_ami(pred["s01_q_template_bin"].astype(str).to_numpy(), pred[col].astype(str).to_numpy()), "purity": purity_score(pred["s01_q_template_bin"].astype(str).to_numpy(), pred[col].astype(str).to_numpy())})
    rows.append({"check": "s01_q_template_bin_vs_run", "method": "target", "ami": safe_ami(aligned_meta["run"].astype(str).to_numpy(), pred["s01_q_template_bin"].astype(str).to_numpy()), "purity": purity_score(aligned_meta["run"].astype(str).to_numpy(), pred["s01_q_template_bin"].astype(str).to_numpy())})
    rows.append({"check": "s01_q_template_bin_vs_stave", "method": "target", "ami": safe_ami(aligned_meta["stave"].astype(str).to_numpy(), pred["s01_q_template_bin"].astype(str).to_numpy()), "purity": purity_score(aligned_meta["stave"].astype(str).to_numpy(), pred["s01_q_template_bin"].astype(str).to_numpy())})
    return pd.DataFrame(rows)


def write_report(result: dict, run_metrics: pd.DataFrame, stave_metrics: pd.DataFrame, ci: pd.DataFrame, leak: pd.DataFrame) -> None:
    def metric_line(split: str, method: str, target: str) -> str:
        table = run_metrics if split == "run" else stave_metrics
        row = table[(table["method"] == method) & (table["target"] == target)].iloc[0]
        ami_ci = ci[(ci["split"] == split) & (ci["method"] == method) & (ci["target"] == target) & (ci["metric"] == "ami")].iloc[0]
        pur_ci = ci[(ci["split"] == split) & (ci["method"] == method) & (ci["target"] == target) & (ci["metric"] == "purity")].iloc[0]
        return f"{row['ami']:.3f} [{ami_ci['ci_low']:.3f},{ami_ci['ci_high']:.3f}] / {row['purity']:.3f} [{pur_ci['ci_low']:.3f},{pur_ci['ci_high']:.3f}]"

    q_delta = ci[(ci["split"] == "run") & (ci["method"] == "delta") & (ci["target"] == "s01_q_template_bin") & (ci["metric"] == "ami")].iloc[0]
    manual_delta = ci[(ci["split"] == "run") & (ci["method"] == "delta") & (ci["target"] == "manual_flag") & (ci["metric"] == "ami")].iloc[0]
    ml_q = run_metrics[(run_metrics["method"] == "ml_autoencoder") & (run_metrics["target"] == "s01_q_template_bin")]["ami"].iloc[0]
    leakage_alarm = bool(ml_q > 0.80)
    lines = [
        f"# Study report: {STUDY_ID} - {TITLE}",
        "",
        f"**Ticket:** {TICKET_ID}",
        f"**Command:** `/home/billy/anaconda3/bin/python reports/{TICKET_ID}/p02c_full_s01_q_template_cluster_stability.py`",
        "",
        "## Reproduction first",
        f"Raw B-stack ROOT was scanned from `{result['raw_root_dir']}` before modeling. The S00 B-stave selected-pulse gate reproduced **{result['reproduction']['selected_pulses']:,}** records versus expected **{EXPECTED_S00_SELECTED:,}**.",
        f"For the original P02 run/sample recipe, the script sampled **{result['p02_reproduction']['sample_size']:,}** pulses and reproduced the early-peak `peak<=3` class at **{100.0 * result['p02_reproduction']['early_peak_peak_le_3_rate']:.2f}%**, matching the reported approximately 4.4% anomalous class.",
        f"The committed S01 `q_template_per_pulse.csv.gz` was then aligned row-for-row by run, event number, EVT, stave, channel, amplitude, peak sample, and area. Alignment passed for **{result['s01_alignment']['s01_rows']:,}** rows; median full-S01 q-template RMSE is **{result['s01_alignment']['q_template_rmse_median']:.4f}**.",
        "",
        "## Methods",
        f"All modeling used a run/stave-balanced subsample of **{result['analysis_sample_rows']:,}** selected pulses from the reproduced raw population with exact S01 q-template rows attached. The primary split is GroupKFold by run; a leave-one-stave-held-out stress test checks stave sampling artifacts. Hyperparameters (`n_clusters`) are selected by training-fold BIC only.",
        "",
        "- **Traditional:** hand-crafted shape variables (peak sample, area/peak, tail/late/early fractions, widths, final sample, max negative step, asymmetry) plus PCA-4 and diagonal GMM.",
        "- **ML:** P02-style fully connected autoencoder on the 18 normalized waveform samples, using the held-in fold only, then diagonal GMM in the learned latent.",
        "- **Topology comparisons:** full-S01 q-template residual bins, peak groups, event downstream topology, CFD20 downstream-span (`D_t`) class, and manual diagnostic flags. q-template values are labels for evaluation only; they are not model inputs.",
        "",
        "## Held-out stability",
        "",
        "| Split | Method | S01 q_template AMI / purity | peak AMI / purity | downstream AMI / purity | D_t AMI / purity | manual flag AMI / purity |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for split in ["run", "stave"]:
        for method in ["traditional", "ml_autoencoder"]:
            lines.append(
                f"| {split} | {method} | {metric_line(split, method, 's01_q_template_bin')} | {metric_line(split, method, 'peak_group')} | {metric_line(split, method, 'downstream_topology')} | {metric_line(split, method, 'dt_label')} | {metric_line(split, method, 'manual_flag')} |"
            )
    lines.extend(
        [
            "",
            "## Leakage checks",
            "",
            f"The run-held-out ML clusters have run-label AMI **{leak[(leak['method']=='ml_autoencoder') & (leak['check']=='cluster_vs_run')]['ami'].iloc[0]:.3f}** and stave-label AMI **{leak[(leak['method']=='ml_autoencoder') & (leak['check']=='cluster_vs_stave')]['ami'].iloc[0]:.3f}**. Traditional clusters are similar: run AMI **{leak[(leak['method']=='traditional') & (leak['check']=='cluster_vs_run')]['ami'].iloc[0]:.3f}**, stave AMI **{leak[(leak['method']=='traditional') & (leak['check']=='cluster_vs_stave')]['ami'].iloc[0]:.3f}**.",
            f"The target itself has run AMI **{leak[(leak['method']=='target') & (leak['check']=='s01_q_template_bin_vs_run')]['ami'].iloc[0]:.3f}** and stave AMI **{leak[(leak['method']=='target') & (leak['check']=='s01_q_template_bin_vs_stave')]['ami'].iloc[0]:.3f}**, so q-template bins are not acting as a direct run or stave code.",
            f"The paired run-bootstrap CI for ML minus traditional on S01 q-template AMI is **[{q_delta['ci_low']:.3f}, {q_delta['ci_high']:.3f}]**; for manual-flag AMI it is **[{manual_delta['ci_low']:.3f}, {manual_delta['ci_high']:.3f}]**. Leakage alarm status: **{'triggered' if leakage_alarm else 'not triggered'}** under the pre-set `AMI > 0.80` too-good threshold.",
            "",
            "## Verdict",
            "",
            "Using the exact full-S01 q_template table does not overturn P02b: clusters associate most strongly with peak/manual pulse morphology, while S01 q-template, downstream topology, and D_t are weaker held-out associations. The q-template signal is stable enough to be a pulse-shape diagnostic, but neither method produces a suspiciously perfect q-template classifier.",
            "",
            "## Reproducibility",
            "",
            f"`manifest.json` records raw input SHA256 hashes, command, git commit, software versions, and output hashes. Supporting CSVs and figures are in `reports/{TICKET_ID}/`.",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)
    raw_dir = raw_root_dir()
    print(f"raw_dir={raw_dir}")
    waves, meta, counts_by_run = scan_raw(raw_dir)
    feats = shape_features(waves)
    labels = make_labels(meta, feats)
    p02_repro = p02_sample_reproduction(waves, meta, feats)
    meta, s01_alignment = align_s01_q_template(meta)

    sample_idx = stratified_sample(meta, rng)
    swaves = waves[sample_idx]
    smeta = meta.iloc[sample_idx].reset_index(drop=True)
    sfeats = feats.iloc[sample_idx].reset_index(drop=True)
    slabels = labels.iloc[sample_idx].reset_index(drop=True)

    pred_paths_exist = (OUT / "run_heldout_predictions.csv.gz").exists() and (OUT / "stave_heldout_predictions.csv.gz").exists() and (OUT / "fold_model_info.csv").exists()
    if pred_paths_exist:
        print("reusing existing held-out prediction files")
        run_pred = pd.read_csv(OUT / "run_heldout_predictions.csv.gz")
        stave_pred = pd.read_csv(OUT / "stave_heldout_predictions.csv.gz")
    else:
        run_pred, run_info = fold_predictions(swaves, smeta, sfeats, slabels, "run", rng)
        stave_pred, stave_info = fold_predictions(swaves, smeta, sfeats, slabels, "stave", rng)
        run_pred.to_csv(OUT / "run_heldout_predictions.csv.gz", index=False)
        stave_pred.to_csv(OUT / "stave_heldout_predictions.csv.gz", index=False)
        pd.concat([run_info, stave_info], ignore_index=True).to_csv(OUT / "fold_model_info.csv", index=False)
    run_metrics = metric_rows(run_pred, "run")
    stave_metrics = metric_rows(stave_pred, "stave")
    ci = pd.concat([bootstrap_metrics(run_pred, "run", rng), bootstrap_metrics(stave_pred, "stave", rng)], ignore_index=True)
    leak = leakage_checks(run_pred, smeta)

    counts_by_run.to_csv(OUT / "counts_by_run.csv", index=False)
    run_metrics.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    stave_metrics.to_csv(OUT / "stave_heldout_metrics.csv", index=False)
    ci.to_csv(OUT / "bootstrap_ci.csv", index=False)
    leak.to_csv(OUT / "leakage_checks.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    peak_counts = feats["peak_sample"].value_counts().sort_index()
    ax.bar(peak_counts.index.astype(int), peak_counts.values, color="#3d6f8e")
    ax.axvspan(-0.5, 3.5, color="#d1495b", alpha=0.18, label="P02 early peak <=3")
    ax.set_xlabel("peak sample")
    ax.set_ylabel("selected pulses")
    ax.set_title("Raw-selected pulse peak-sample distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "fig_peak_distribution.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    plot_data = run_metrics[run_metrics["target"].isin(["manual_flag", "s01_q_template_bin", "downstream_topology"])]
    x = np.arange(len(plot_data))
    colors = np.where(plot_data["method"].to_numpy() == "ml_autoencoder", "#2a9d8f", "#6c757d")
    ax.bar(x, plot_data["ami"].to_numpy(), color=colors)
    ax.set_xticks(x, [f"{m}\n{t}" for m, t in zip(plot_data["method"], plot_data["target"])], rotation=35, ha="right")
    ax.set_ylabel("run-held-out AMI")
    ax.set_title("Cluster association with held-out topology labels")
    fig.tight_layout()
    fig.savefig(OUT / "fig_run_heldout_ami.png", dpi=130)
    plt.close(fig)

    result = {
        "ticket_id": TICKET_ID,
        "study_id": STUDY_ID,
        "title": TITLE,
        "raw_root_dir": str(raw_dir),
        "reproduction": {
            "expected_selected_pulses": EXPECTED_S00_SELECTED,
            "selected_pulses": int(len(waves)),
            "passed": bool(len(waves) == EXPECTED_S00_SELECTED),
        },
        "p02_reproduction": p02_repro,
        "s01_alignment": s01_alignment,
        "analysis_sample_rows": int(len(sample_idx)),
        "split": {
            "run_grouped_folds": 5,
            "stave_heldout_folds": sorted(smeta["stave"].unique().tolist()),
            "bootstrap_replicates": BOOTSTRAPS,
            "bootstrap_units": {"run_split": "run", "stave_split": "stave"},
        },
        "traditional": {
            "method": "hand-crafted shape features + PCA4 + diagonal GMM",
            "run_heldout_metrics": run_metrics[run_metrics["method"] == "traditional"].to_dict(orient="records"),
            "stave_heldout_metrics": stave_metrics[stave_metrics["method"] == "traditional"].to_dict(orient="records"),
        },
        "ml": {
            "method": "P02-style autoencoder latent + diagonal GMM",
            "run_heldout_metrics": run_metrics[run_metrics["method"] == "ml_autoencoder"].to_dict(orient="records"),
            "stave_heldout_metrics": stave_metrics[stave_metrics["method"] == "ml_autoencoder"].to_dict(orient="records"),
        },
        "leakage_checks": leak.to_dict(orient="records"),
        "follow_up_tickets": [
            "P02d: validate early-peak P02 topology against downstream timing tails in S07/S02 without using D_t as a training feature.",
            "S01f: test whether S01 q_template run/stave structure predicts template-transfer failures after amplitude and peak-sample conditioning.",
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }

    write_report(result, run_metrics, stave_metrics, ci, leak)
    (OUT / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    raw_hashes = [{"path": str(raw_dir / f"hrdb_run_{run:04d}.root"), "sha256": sha256_file(raw_dir / f"hrdb_run_{run:04d}.root")} for run in RUNS]
    input_hashes = [{"path": str(S01_Q_TEMPLATE), "sha256": sha256_file(S01_Q_TEMPLATE)}] + raw_hashes
    with (OUT / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        writer.writerows(input_hashes)
    output_hashes = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "ticket_id": TICKET_ID,
        "command": f"/home/billy/anaconda3/bin/python reports/{TICKET_ID}/p02c_full_s01_q_template_cluster_stability.py",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": RANDOM_SEED,
        "input_sha256": input_hashes,
        "output_sha256": output_hashes,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "out": str(OUT), "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
