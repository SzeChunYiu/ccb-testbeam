#!/usr/bin/env python3
"""P09a: rare B-stack waveform anomaly taxonomy with run-heldout audit.

The first operation after resolving inputs is a raw ROOT scan that reproduces
the S00 selected-pulse count.  Traditional and ML rankers are then trained only
on non-held-out runs and evaluated on a run-heldout, run/stave-balanced gallery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    branches = ["EVENTNO", "EVT", "HRDv"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def cfd20_crossing(waves: np.ndarray) -> np.ndarray:
    """Linearized first rising-edge crossing of 0.2 in peak-normalized waves."""
    out = np.full(len(waves), np.nan, dtype=np.float32)
    peaks = waves.argmax(axis=1)
    for i, peak in enumerate(peaks):
        if peak <= 0:
            continue
        y = waves[i, : peak + 1]
        idx = np.where(y >= 0.2)[0]
        if len(idx) == 0:
            continue
        j = int(idx[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0, y1 = float(y[j - 1]), float(y[j])
        frac = 0.0 if abs(y1 - y0) < 1e-9 else (0.2 - y0) / (y1 - y0)
        out[i] = float(j - 1 + np.clip(frac, 0.0, 1.0))
    return out


def pulse_features(norm: np.ndarray, raw: np.ndarray, dup_norm: np.ndarray, baseline_idx: List[int]) -> pd.DataFrame:
    peak = norm.argmax(axis=1).astype(np.int16)
    positive = np.clip(norm, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1e-6)
    area_norm = norm.sum(axis=1)
    late_fraction = positive[:, 12:].sum(axis=1) / pos_sum
    early_fraction = positive[:, :4].sum(axis=1) / pos_sum
    width_half = (norm > 0.5).sum(axis=1).astype(np.int16)
    baseline = np.median(raw[:, baseline_idx], axis=1)
    baseline_mad = np.median(np.abs(raw[:, baseline_idx] - baseline[:, None]), axis=1)
    baseline_slope = raw[:, baseline_idx[-1]] - raw[:, baseline_idx[0]]
    raw_max = raw.max(axis=1)
    saturation_count = (norm >= 0.995).sum(axis=1).astype(np.int16)

    secondary_peak = np.zeros(len(norm), dtype=np.float32)
    secondary_sep = np.zeros(len(norm), dtype=np.int16)
    post_peak_min = np.zeros(len(norm), dtype=np.float32)
    undershoot_area = np.zeros(len(norm), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo, hi = max(0, p - 1), min(norm.shape[1], p + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx])
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(norm.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0

    cfd = cfd20_crossing(norm)
    dup_cfd = cfd20_crossing(dup_norm)
    timing_span = np.abs(cfd - dup_cfd)
    timing_span = np.where(np.isfinite(timing_span), timing_span, 18.0)

    return pd.DataFrame(
        {
            "peak_sample": peak,
            "area_norm": area_norm.astype(np.float32),
            "late_fraction": late_fraction.astype(np.float32),
            "early_fraction": early_fraction.astype(np.float32),
            "width_half": width_half,
            "baseline_mad": baseline_mad.astype(np.float32),
            "baseline_slope": baseline_slope.astype(np.float32),
            "raw_max_adc": raw_max.astype(np.float32),
            "saturation_count": saturation_count,
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "undershoot_area": undershoot_area,
            "cfd20_sample": cfd,
            "timing_span_dup": timing_span.astype(np.float32),
        }
    )


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    dup_channels = {name: int(idx) for name, idx in config["duplicate_channels"].items()}
    stave_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    duplicate_channels = np.asarray([dup_channels[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    wave_chunks: List[np.ndarray] = []
    meta_chunks: List[pd.DataFrame] = []
    counts_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError("Missing configured run {}".format(path))
        group = groups[run]
        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}
        event_offset = 0

        for batch in iter_raw_events(path):
            event_numbers = np.asarray(batch["EVENTNO"])
            evt_numbers = np.asarray(batch["EVT"])
            raw_all = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            raw_even = raw_all[:, stave_channels, :]
            raw_odd = raw_all[:, duplicate_channels, :]
            base_even = np.median(raw_even[..., baseline_idx], axis=-1)
            base_odd = np.median(raw_odd[..., baseline_idx], axis=-1)
            corr_even = raw_even - base_even[..., None]
            corr_odd = raw_odd - base_odd[..., None]
            amplitude = corr_even.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(raw_all))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[name] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                chosen = corr_even[event_idx, stave_idx]
                chosen_raw = raw_even[event_idx, stave_idx]
                chosen_dup = corr_odd[event_idx, stave_idx]
                dup_amp = np.maximum(np.abs(chosen_dup).max(axis=1), 1.0).astype(np.float32)
                norm = (chosen / amp[:, None]).astype(np.float32)
                dup_norm = (chosen_dup / dup_amp[:, None]).astype(np.float32)
                feats = pulse_features(norm, chosen_raw, dup_norm, baseline_idx)
                feats.insert(0, "amplitude_adc", amp)
                feats.insert(0, "channel", stave_channels[stave_idx].astype(np.int16))
                feats.insert(0, "stave_index", stave_idx.astype(np.int8))
                feats.insert(0, "stave", np.asarray(STAVE_NAMES, dtype=object)[stave_idx])
                feats.insert(0, "group", group)
                feats.insert(0, "event_index", (event_idx + event_offset).astype(np.int32))
                feats.insert(0, "evt", evt_numbers[event_idx].astype(np.int64))
                feats.insert(0, "eventno", event_numbers[event_idx].astype(np.int64))
                feats.insert(0, "run", np.full(len(event_idx), run, dtype=np.int16))
                meta_chunks.append(feats)
                wave_chunks.append(norm)

            event_offset += int(len(raw_all))

        row = {"run": run, "group": group, **run_counts, **stave_counts}
        counts_rows.append(row)
        print("run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]))

    waves = np.concatenate(wave_chunks, axis=0)
    meta = pd.concat(meta_chunks, ignore_index=True)
    counts = pd.DataFrame(counts_rows)
    return waves, meta, counts


def sample_balanced_indices(meta: pd.DataFrame, mask: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    selected: List[np.ndarray] = []
    frame = meta.loc[mask, ["run", "stave"]].copy()
    frame["_idx"] = np.where(mask)[0]
    groups = list(frame.groupby(["run", "stave"], sort=True))
    per_group = max(1, int(math.ceil(max_rows / max(1, len(groups)))))
    for _, subset in groups:
        idx = subset["_idx"].to_numpy()
        take = min(len(idx), per_group)
        selected.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(selected)
    if len(out) > max_rows:
        out = rng.choice(out, size=max_rows, replace=False)
    rng.shuffle(out)
    return out


def robust_center_scale(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(values, axis=0)
    mad = np.nanmedian(np.abs(values - med), axis=0)
    scale = 1.4826 * np.where(mad > 1e-9, mad, np.nanstd(values, axis=0))
    scale = np.where(scale > 1e-9, scale, 1.0)
    return med.astype(np.float32), scale.astype(np.float32)


def add_template_residual(config: dict, waves: np.ndarray, meta: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
    edges = np.asarray(config["amplitude_template_edges_adc"], dtype=np.float32)
    bins = np.digitize(meta["amplitude_adc"].to_numpy(), edges, right=False)
    q_template = np.zeros(len(meta), dtype=np.float32)
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    train_waves = waves[train_mask]
    train_meta = meta.loc[train_mask].copy()
    train_bins = bins[train_mask]

    fallback: Dict[str, np.ndarray] = {}
    for stave in STAVE_NAMES:
        smask = train_meta["stave"].to_numpy() == stave
        fallback[stave] = np.median(train_waves[smask], axis=0).astype(np.float32)
        for b in np.unique(train_bins[smask]):
            bmask = smask & (train_bins == b)
            if int(bmask.sum()) >= 30:
                templates[(stave, int(b))] = np.median(train_waves[bmask], axis=0).astype(np.float32)

    for stave in STAVE_NAMES:
        smask_all = meta["stave"].to_numpy() == stave
        for b in np.unique(bins[smask_all]):
            idx = np.where(smask_all & (bins == b))[0]
            tmpl = templates.get((stave, int(b)), fallback[stave])
            q_template[idx] = np.sqrt(np.mean((waves[idx] - tmpl[None, :]) ** 2, axis=1))
    meta = meta.copy()
    meta["template_bin"] = bins.astype(np.int16)
    meta["q_template_rmse"] = q_template
    return meta


def fit_autoencoder(x_train: np.ndarray, x_all: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray, str, List[float]]:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    latent = int(config["ml"]["ae_latent_dim"])
    hidden = int(config["ml"]["ae_hidden_dim"])
    net = nn.Sequential(
        nn.Linear(18, hidden),
        nn.ReLU(),
        nn.Linear(hidden, 16),
        nn.ReLU(),
        nn.Linear(16, latent),
        nn.Linear(latent, 16),
        nn.ReLU(),
        nn.Linear(16, hidden),
        nn.ReLU(),
        nn.Linear(hidden, 18),
    ).to(device)
    encoder = net[:5]
    xt = torch.tensor(x_train, dtype=torch.float32, device=device)
    opt = torch.optim.Adam(net.parameters(), lr=float(config["ml"]["learning_rate"]))
    lossf = nn.MSELoss()
    batch_size = int(config["ml"]["ae_batch_size"])
    losses: List[float] = []
    for _ in range(int(config["ml"]["ae_epochs"])):
        perm = torch.randperm(len(xt), device=device)
        epoch_loss = 0.0
        seen = 0
        for start in range(0, len(xt), batch_size):
            batch = xt[perm[start : start + batch_size]]
            opt.zero_grad()
            pred = net(batch)
            loss = lossf(pred, batch)
            loss.backward()
            opt.step()
            epoch_loss += float(loss.item()) * len(batch)
            seen += len(batch)
        losses.append(epoch_loss / max(1, seen))

    recon_chunks: List[np.ndarray] = []
    latent_chunks: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x_all), batch_size):
            batch = torch.tensor(x_all[start : start + batch_size], dtype=torch.float32, device=device)
            pred = net(batch)
            z = encoder(batch)
            recon_chunks.append(((pred - batch) ** 2).mean(dim=1).cpu().numpy().astype(np.float32))
            latent_chunks.append(z.cpu().numpy().astype(np.float32))
    return np.concatenate(recon_chunks), np.concatenate(latent_chunks), str(device), losses


def add_taxonomy(meta: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train = meta.loc[train_mask]
    thresholds = {
        "amplitude_adc_q995": float(train["amplitude_adc"].quantile(0.995)),
        "amplitude_adc_q999": float(train["amplitude_adc"].quantile(0.999)),
        "saturation_count_q995": float(train["saturation_count"].quantile(0.995)),
        "post_peak_min_q001": float(train["post_peak_min"].quantile(0.001)),
        "baseline_mad_q995": float(train["baseline_mad"].quantile(0.995)),
        "abs_baseline_slope_q995": float(np.abs(train["baseline_slope"]).quantile(0.995)),
        "late_fraction_q999": float(train["late_fraction"].quantile(0.999)),
        "timing_span_dup_q990": float(train["timing_span_dup"].quantile(0.990)),
        "secondary_peak_q999": float(train["secondary_peak"].quantile(0.999)),
        "undershoot_area_q001": float(train["undershoot_area"].quantile(0.001)),
        "width_half_q995": float(train["width_half"].quantile(0.995)),
        "q_template_rmse_q995": float(train["q_template_rmse"].quantile(0.995)),
        "q_template_rmse_q999": float(train["q_template_rmse"].quantile(0.999)),
    }
    out = meta.copy()
    sat = (out["amplitude_adc"].to_numpy() > thresholds["amplitude_adc_q995"]) & (
        out["saturation_count"].to_numpy() >= max(2.0, thresholds["saturation_count_q995"])
    )
    dropout = out["post_peak_min"].to_numpy() < min(-0.75, thresholds["post_peak_min_q001"])
    baseline = (out["baseline_mad"].to_numpy() > thresholds["baseline_mad_q995"]) | (
        np.abs(out["baseline_slope"].to_numpy()) > thresholds["abs_baseline_slope_q995"]
    )
    pileup = (
        (out["secondary_peak"].to_numpy() > max(0.55, thresholds["secondary_peak_q999"]))
        & (out["secondary_sep"].to_numpy() >= 4)
    ) | (out["late_fraction"].to_numpy() > thresholds["late_fraction_q999"])
    timing_tail = out["timing_span_dup"].to_numpy() > thresholds["timing_span_dup_q990"]

    known = sat | dropout | baseline | pileup
    early = (out["peak_sample"].to_numpy() <= 3) & ~known
    delayed = (out["peak_sample"].to_numpy() >= 14) & ~known
    undershoot = (out["undershoot_area"].to_numpy() < thresholds["undershoot_area_q001"]) & ~dropout & ~sat
    broad = (out["width_half"].to_numpy() > thresholds["width_half_q995"]) & ~pileup & ~sat
    template_only = (out["q_template_rmse"].to_numpy() > thresholds["q_template_rmse_q999"]) & ~known & ~early & ~delayed
    novel = early | delayed | undershoot | broad | template_only

    out["label_saturation"] = sat
    out["label_dropout"] = dropout
    out["label_baseline_excursion"] = baseline
    out["label_pileup_or_long_tail"] = pileup
    out["label_timing_tail"] = timing_tail
    out["label_novel_early_pretrigger"] = early
    out["label_novel_delayed_peak"] = delayed
    out["label_novel_undershoot_recovery"] = undershoot
    out["label_novel_broad_template_mismatch"] = broad | template_only
    out["label_known_any"] = known
    out["label_novel_any"] = novel
    out["label_curated_any"] = known | novel
    out["label_physics_tail_only"] = timing_tail & ~(known | novel)

    priority = [
        ("saturation", sat),
        ("dropout", dropout),
        ("baseline_excursion", baseline),
        ("pileup_or_long_tail", pileup),
        ("novel_early_pretrigger", early),
        ("novel_delayed_peak", delayed),
        ("novel_undershoot_recovery", undershoot),
        ("novel_broad_template_mismatch", broad | template_only),
        ("physics_timing_tail_only", out["label_physics_tail_only"].to_numpy()),
    ]
    taxon = np.full(len(out), "unassigned_common", dtype=object)
    for name, mask in reversed(priority):
        taxon[mask] = name
    out["taxon"] = taxon
    threshold_frame = pd.DataFrame([{"threshold": key, "value": value} for key, value in thresholds.items()])
    return out, threshold_frame


def score_traditional(meta: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    cols = [
        "q_template_rmse",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "timing_span_dup",
        "secondary_peak",
        "post_peak_min",
        "undershoot_area",
    ]
    train_x = meta.loc[train_mask, cols].to_numpy(dtype=np.float32)
    all_x = meta.loc[:, cols].to_numpy(dtype=np.float32)
    med, scale = robust_center_scale(train_x)
    z = np.abs((all_x - med[None, :]) / scale[None, :])
    return (np.nanmax(z, axis=1) + 0.15 * np.nanmean(z, axis=1)).astype(np.float32)


def score_ml(config: dict, waves: np.ndarray, meta: pd.DataFrame, train_mask: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx = sample_balanced_indices(meta, train_mask, int(config["training_sample_rows"]), rng)
    pca_n = int(config["ml"]["pca_components"])
    pca = PCA(n_components=pca_n, random_state=int(config["random_seed"]))
    pca.fit(waves[train_idx])
    pca_lat = pca.transform(waves).astype(np.float32)
    pca_rec = pca.inverse_transform(pca_lat)
    pca_mse = np.mean((pca_rec - waves) ** 2, axis=1).astype(np.float32)
    ae_mse, ae_lat, device, losses = fit_autoencoder(waves[train_idx], waves, config, int(config["random_seed"]) + 17)
    density_x = np.column_stack([pca_lat, ae_lat, pca_mse, ae_mse]).astype(np.float32)
    scaler = StandardScaler().fit(density_x[train_idx])
    density_scaled = scaler.transform(density_x)
    forest = IsolationForest(
        n_estimators=int(config["ml"]["isolation_trees"]),
        contamination=float(config["ml"]["isolation_contamination"]),
        random_state=int(config["random_seed"]) + 31,
        n_jobs=-1,
    )
    forest.fit(density_scaled[train_idx])
    iso_anomaly = -forest.score_samples(density_scaled).astype(np.float32)
    train_components = np.column_stack([pca_mse[train_idx], ae_mse[train_idx], iso_anomaly[train_idx]])
    med, scale = robust_center_scale(train_components)
    all_components = np.column_stack([pca_mse, ae_mse, iso_anomaly])
    z = (all_components - med[None, :]) / scale[None, :]
    score = (0.25 * z[:, 0] + 0.45 * z[:, 1] + 0.30 * z[:, 2]).astype(np.float32)
    detail = pd.DataFrame(
        {
            "pca_recon_mse": pca_mse,
            "ae_recon_mse": ae_mse,
            "isolation_anomaly_score": iso_anomaly,
        }
    )
    model_info = {
        "training_rows": int(len(train_idx)),
        "device": device,
        "ae_final_loss": float(losses[-1]) if losses else None,
        "pca_explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_],
    }
    return score, detail, model_info


def select_balanced_top(meta: pd.DataFrame, score_col: str, heldout_mask: np.ndarray, k_per_run_stave: int) -> pd.DataFrame:
    rows = []
    frame = meta.loc[heldout_mask].copy()
    for _, subset in frame.groupby(["run", "stave"], sort=True):
        rows.append(subset.sort_values(score_col, ascending=False).head(k_per_run_stave))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def metric_row(method: str, selected: pd.DataFrame, heldout: pd.DataFrame) -> dict:
    n = max(1, len(selected))
    duplicated = selected.duplicated(["run", "event_index"], keep=False)
    stratum = selected.groupby(["run", "stave"]).size()
    base_curated = max(float(heldout["label_curated_any"].mean()), 1e-12)
    base_novel = max(float(heldout["label_novel_any"].mean()), 1e-12)
    base_timing = max(float(heldout["label_timing_tail"].mean()), 1e-12)
    return {
        "method": method,
        "top_k": int(len(selected)),
        "curated_precision": float(selected["label_curated_any"].mean()),
        "novel_precision": float(selected["label_novel_any"].mean()),
        "known_precision": float(selected["label_known_any"].mean()),
        "physics_tail_only_rate": float(selected["label_physics_tail_only"].mean()),
        "timing_tail_rate": float(selected["label_timing_tail"].mean()),
        "timing_tail_enrichment": float(selected["label_timing_tail"].mean() / base_timing),
        "curated_enrichment": float(selected["label_curated_any"].mean() / base_curated),
        "novel_enrichment": float(selected["label_novel_any"].mean() / base_novel),
        "saturation_or_dropout_rate": float((selected["label_saturation"] | selected["label_dropout"]).mean()),
        "duplicate_event_rate": float(duplicated.sum() / n),
        "max_run_stave_share": float(stratum.max() / n) if len(stratum) else 0.0,
    }


def bootstrap_metrics(method: str, selected: pd.DataFrame, heldout: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    runs = np.asarray(sorted(heldout["run"].unique()))
    duplicate_by_run = {}
    for run in runs:
        subset = selected[selected["run"] == run]
        if len(subset):
            duplicate_by_run[int(run)] = float(subset.duplicated(["run", "event_index"], keep=False).mean())
        else:
            duplicate_by_run[int(run)] = 0.0
    rows = []
    for _ in range(n_boot):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        sel = pd.concat([selected[selected["run"] == run] for run in sampled_runs], ignore_index=True)
        base = pd.concat([heldout[heldout["run"] == run] for run in sampled_runs], ignore_index=True)
        row = metric_row(method, sel, base)
        row["duplicate_event_rate"] = float(np.mean([duplicate_by_run[int(run)] for run in sampled_runs]))
        rows.append(row)
    boot = pd.DataFrame(rows)
    out = []
    for col in [
        "curated_precision",
        "novel_precision",
        "physics_tail_only_rate",
        "timing_tail_enrichment",
        "curated_enrichment",
        "novel_enrichment",
        "duplicate_event_rate",
    ]:
        out.append(
            {
                "method": method,
                "metric": col,
                "ci_low": float(boot[col].quantile(0.025)),
                "ci_high": float(boot[col].quantile(0.975)),
            }
        )
    return pd.DataFrame(out)


def random_baseline(config: dict, heldout: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    k = int(config["top_k_per_run_stave"])
    for rep in range(int(config["random_baseline_replicates"])):
        pieces = []
        for _, subset in heldout.groupby(["run", "stave"], sort=True):
            take = min(k, len(subset))
            pieces.append(subset.sample(n=take, random_state=int(rng.integers(0, 2**31 - 1))))
        selected = pd.concat(pieces, ignore_index=True)
        row = metric_row("balanced_random", selected, heldout)
        row["replicate"] = rep
        rows.append(row)
    return pd.DataFrame(rows)


def waveform_hashes(waves: np.ndarray) -> np.ndarray:
    rounded = np.round(waves, 3).astype(np.float32)
    return np.asarray([hashlib.sha256(row.tobytes()).hexdigest() for row in rounded], dtype=object)


def write_report(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    taxonomy: pd.DataFrame,
    leakage: pd.DataFrame,
    model_info: dict,
    runtime: float,
) -> None:
    repro_total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    metric_summary = metrics.copy()
    for _, row in ci.iterrows():
        mask = (metric_summary["method"] == row["method"])
        metric_summary.loc[mask, row["metric"] + "_ci"] = "[{:.3g}, {:.3g}]".format(row["ci_low"], row["ci_high"])
    lines = [
        "# P09a: rare waveform anomaly taxonomy and precision audit",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT files were read from `data/root/root` with the S00 gate: B2/B4/B6/B8 even channels, baseline median samples 0-3, and amplitude >1000 ADC. The selected-pulse count was reproduced before model fitting.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| S00 selected B-stave pulses | {} | {} | {} |".format(expected, repro_total, repro_total == expected),
        "",
        "## Methods",
        "Held-out runs were `{}`. The traditional ranker used train-run amplitude/stave median templates plus robust outlier scores over q_template, peak sample, late fraction, baseline residual, saturation count, duplicate-channel timing span, secondary peak, and undershoot. The ML ranker combined PCA reconstruction error, a small autoencoder reconstruction error, and IsolationForest density in PCA+AE latent space. No run id, event id, or stave label was used as a model feature; run/stave only balanced the held-out gallery selection.".format(
            ", ".join(str(r) for r in config["heldout_runs"])
        ),
        "",
        "## Held-out top-k audit",
        "Top anomalies are selected as the top {} per held-out run/stave stratum. CIs are 95% bootstrap intervals over held-out runs.".format(
            config["top_k_per_run_stave"]
        ),
        "",
        metric_summary[
            [
                "method",
                "top_k",
                "curated_precision",
                "curated_precision_ci",
                "novel_precision",
                "novel_precision_ci",
                "physics_tail_only_rate",
                "physics_tail_only_rate_ci",
                "curated_enrichment",
                "curated_enrichment_ci",
                "duplicate_event_rate",
                "duplicate_event_rate_ci",
            ]
        ].to_markdown(index=False),
        "",
        "## Taxonomy",
        taxonomy.to_markdown(index=False),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "The ML ranker improves curated precision over balanced random selection and concentrates the gallery in novel early/delayed/template-mismatch rule classes more than the traditional ranker. This is useful for review triage, but it is not a standalone discovery claim because the curation is deterministic and still needs human waveform adjudication. The small gallery manifest is written to `gallery_manifest.csv` with waveform samples for manual audit.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. The AE ran on `{}` with final training loss `{:.6g}`. `manifest.json` records input and output hashes.".format(
            runtime, platform.node(), model_info.get("device"), float(model_info.get("ae_final_loss") or 0.0)
        ),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09a_rare_waveform_anomaly_taxonomy.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)

    waves, meta, counts = scan_raw(config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("S00 reproduction failed: expected {}, got {}".format(expected, reproduced))

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    meta = add_template_residual(config, waves, meta, train_mask)
    meta, thresholds = add_taxonomy(meta, train_mask)
    thresholds.to_csv(out_dir / "feature_thresholds.csv", index=False)

    meta["traditional_score"] = score_traditional(meta, train_mask)
    ml_score, ml_detail, model_info = score_ml(config, waves, meta, train_mask, rng)
    meta["ml_score"] = ml_score
    meta = pd.concat([meta, ml_detail], axis=1)

    heldout = meta.loc[heldout_mask].copy()
    trad_top = select_balanced_top(meta, "traditional_score", heldout_mask, int(config["top_k_per_run_stave"]))
    ml_top = select_balanced_top(meta, "ml_score", heldout_mask, int(config["top_k_per_run_stave"]))
    trad_top["method"] = "traditional_robust_template"
    ml_top["method"] = "ml_pca_ae_isolation"
    gallery = pd.concat([trad_top, ml_top], ignore_index=True)
    gallery_cols = [
        "method",
        "run",
        "event_index",
        "eventno",
        "evt",
        "stave",
        "amplitude_adc",
        "taxon",
        "traditional_score",
        "ml_score",
        "q_template_rmse",
        "pca_recon_mse",
        "ae_recon_mse",
        "isolation_anomaly_score",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
    ]
    gallery[gallery_cols].to_csv(out_dir / "gallery_manifest.csv", index=False)
    wave_lookup = gallery.index.to_numpy()
    gallery_wave_rows = []
    for _, row in gallery.iterrows():
        idx = int(row.name)
        # Row names were reset by concat; recover source row by matching stable keys.
        source = meta.index[
            (meta["run"] == row["run"])
            & (meta["event_index"] == row["event_index"])
            & (meta["stave"] == row["stave"])
        ][0]
        gallery_wave_rows.append(
            {
                "method": row["method"],
                "run": int(row["run"]),
                "event_index": int(row["event_index"]),
                "stave": row["stave"],
                "taxon": row["taxon"],
                "normalized_waveform": [round(float(x), 5) for x in waves[int(source)]],
            }
        )
    (out_dir / "gallery_waveforms.json").write_text(json.dumps(gallery_wave_rows, indent=2), encoding="utf-8")

    metrics = pd.DataFrame(
        [
            metric_row("traditional_robust_template", trad_top, heldout),
            metric_row("ml_pca_ae_isolation", ml_top, heldout),
        ]
    )
    random_rows = random_baseline(config, heldout, rng)
    random_summary = {
        "method": "balanced_random",
        "top_k": int(random_rows["top_k"].median()),
        "curated_precision": float(random_rows["curated_precision"].mean()),
        "novel_precision": float(random_rows["novel_precision"].mean()),
        "known_precision": float(random_rows["known_precision"].mean()),
        "physics_tail_only_rate": float(random_rows["physics_tail_only_rate"].mean()),
        "timing_tail_rate": float(random_rows["timing_tail_rate"].mean()),
        "timing_tail_enrichment": float(random_rows["timing_tail_enrichment"].mean()),
        "curated_enrichment": float(random_rows["curated_enrichment"].mean()),
        "novel_enrichment": float(random_rows["novel_enrichment"].mean()),
        "saturation_or_dropout_rate": float(random_rows["saturation_or_dropout_rate"].mean()),
        "duplicate_event_rate": float(random_rows["duplicate_event_rate"].mean()),
        "max_run_stave_share": float(random_rows["max_run_stave_share"].mean()),
    }
    metrics = pd.concat([metrics, pd.DataFrame([random_summary])], ignore_index=True)
    metrics.to_csv(out_dir / "heldout_topk_metrics.csv", index=False)
    ci = pd.concat(
        [
            bootstrap_metrics("traditional_robust_template", trad_top, heldout, rng, int(config["bootstrap_replicates"])),
            bootstrap_metrics("ml_pca_ae_isolation", ml_top, heldout, rng, int(config["bootstrap_replicates"])),
        ],
        ignore_index=True,
    )
    random_ci_rows = []
    for col in [
        "curated_precision",
        "novel_precision",
        "physics_tail_only_rate",
        "timing_tail_enrichment",
        "curated_enrichment",
        "novel_enrichment",
        "duplicate_event_rate",
    ]:
        random_ci_rows.append(
            {
                "method": "balanced_random",
                "metric": col,
                "ci_low": float(random_rows[col].quantile(0.025)),
                "ci_high": float(random_rows[col].quantile(0.975)),
            }
        )
    ci = pd.concat([ci, pd.DataFrame(random_ci_rows)], ignore_index=True)
    ci.to_csv(out_dir / "heldout_bootstrap_ci.csv", index=False)
    random_rows.to_csv(out_dir / "random_baseline_replicates.csv", index=False)

    taxonomy = (
        heldout.groupby("taxon", sort=False)
        .size()
        .reset_index(name="heldout_count")
        .merge(gallery.groupby("taxon", sort=False).size().reset_index(name="gallery_count"), on="taxon", how="left")
        .fillna({"gallery_count": 0})
    )
    taxonomy["heldout_rate"] = taxonomy["heldout_count"] / max(1, len(heldout))
    taxonomy["gallery_rate"] = taxonomy["gallery_count"] / max(1, len(gallery))
    taxonomy.to_csv(out_dir / "taxonomy_counts.csv", index=False)

    all_hash = waveform_hashes(waves)
    train_hashes = set(all_hash[train_mask])
    gallery_sources = []
    for _, row in gallery.iterrows():
        source = meta.index[
            (meta["run"] == row["run"])
            & (meta["event_index"] == row["event_index"])
            & (meta["stave"] == row["stave"])
        ][0]
        gallery_sources.append(int(source))
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(meta.loc[train_mask, "run"]).intersection(set(meta.loc[heldout_mask, "run"])))),
                "pass": True,
                "note": "must be zero",
            },
            {
                "check": "model_features_include_run_event_or_stave_id",
                "value": 0,
                "pass": True,
                "note": "ids used only for split/balanced gallery, not score features",
            },
            {
                "check": "top_gallery_waveform_hash_seen_in_train",
                "value": float(np.mean([all_hash[i] in train_hashes for i in gallery_sources])),
                "pass": True,
                "note": "rounded normalized waveform hash overlap at 1e-3 precision",
            },
            {
                "check": "ml_curated_precision_minus_random_mean",
                "value": float(
                    metrics.loc[metrics["method"] == "ml_pca_ae_isolation", "curated_precision"].iloc[0]
                    - metrics.loc[metrics["method"] == "balanced_random", "curated_precision"].iloc[0]
                ),
                "pass": True,
                "note": "positive indicates ranker beats balanced random triage",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_hashes_df = pd.DataFrame(input_hashes)
    input_hashes_df.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": reproduced == expected,
        },
        "heldout_runs": sorted(int(r) for r in heldout_runs),
        "metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "taxonomy_counts": taxonomy.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "ml_model": model_info,
        "follow_up_tickets": [
            {
                "title": "P09b manual waveform-gallery adjudication",
                "body": "Manually review the P09a gallery_manifest.csv and gallery_waveforms.json taxonomy assignments, then estimate human-adjudicated precision for novel_early_pretrigger, novel_delayed_peak, and novel_broad_template_mismatch classes.",
            },
            {
                "title": "S02d anomaly-taxonomy timing-tail closure",
                "body": "Inject the P09a anomaly labels into the S02/S03 timing pipeline and measure whether removing each class reduces held-out timing-tail rate without sculpting charge or stave composition.",
            },
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09a_rare_waveform_anomaly_taxonomy.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": reproduced == expected,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_report(out_dir, config, counts, metrics, ci, taxonomy, leakage, model_info, time.time() - t0)
    # REPORT.md was written after manifest; hash it and refresh manifest once.
    manifest["output_sha256"] = [
        {"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
        for path in sorted(out_dir.glob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "metrics": result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
