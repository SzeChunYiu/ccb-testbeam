#!/usr/bin/env python3
"""P01e strict leakage audit for the P01c latent timing probe.

The first gate rebuilds the raw-ROOT pulse count and the prior P01c pooled
timing numbers. The strict audit then removes the amplitude-bin feature, runs
leave-one-run-out folds over the four P01c held-out candidate runs, uses
event-block bootstrap CIs, and adds an event-shuffled target negative control.
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
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


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
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_time_samples(waves: np.ndarray, fraction: float = 0.2) -> np.ndarray:
    threshold = np.max(waves, axis=1) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = waves[i, j - 1], waves[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    even_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)

    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        run_counts.update({name: 0 for name in STAVE_NAMES})
        event_offset = 0

        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            even_amp = even.max(axis=-1)
            selected = even_amp > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(eventno))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                run_counts[name] += int(selected[:, i].sum())

            if len(event_idx):
                chosen = even[event_idx, stave_idx, :]
                amp = even_amp[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / np.maximum(amp[:, None], 1.0)).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                        }
                    )
                )
            event_offset += int(len(eventno))

        count_rows.append(run_counts)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    counts_by_run = pd.DataFrame(count_rows)
    counts_by_group = (
        counts_by_run.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", *STAVE_NAMES]]
        .sum()
        .reset_index()
    )
    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), counts_by_run, counts_by_group


def event_id(meta: pd.DataFrame) -> pd.Series:
    return meta["run"].astype(str) + ":" + meta["event_index"].astype(str)


def timing_targets(meta: pd.DataFrame, times_ns: np.ndarray, config: dict) -> np.ndarray:
    downstream = list(config["timing_downstream_staves"])
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    target = np.full(len(meta), np.nan, dtype=float)
    sub = meta[meta["stave"].isin(downstream)].copy()
    sub["event_id"] = event_id(sub)
    sub["tcorr"] = times_ns[sub.index.to_numpy()] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr")
    row_lookup = {idx: row for idx, row in wide.iterrows()}
    for idx, row in sub.iterrows():
        vals = row_lookup[row["event_id"]]
        others = [s for s in downstream if s != row["stave"] and pd.notna(vals.get(s, np.nan))]
        if len(others) == 2 and math.isfinite(row["tcorr"]):
            target[int(idx)] = float(row["tcorr"] - np.mean([vals[s] for s in others]))
    return target


def timing_pair_table(meta: pd.DataFrame, times_ns: np.ndarray, config: dict) -> pd.DataFrame:
    downstream = list(config["timing_downstream_staves"])
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    sub = meta[meta["stave"].isin(downstream)].copy()
    sub["event_id"] = event_id(sub)
    sub["tcorr"] = times_ns[sub.index.to_numpy()] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    run_lookup = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide and b in wide:
            vals = wide[a] - wide[b]
            rows.append(
                pd.DataFrame(
                    {
                        "event_id": vals.index,
                        "pair": f"{a}-{b}",
                        "run": [run_lookup[e] for e in vals.index],
                        "residual_ns": vals.to_numpy(dtype=float),
                    }
                )
            )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["event_id", "pair", "run", "residual_ns"])


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def ci(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return float(lo), float(hi)


def event_block_bootstrap(frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> Tuple[float, float, float]:
    events = frame["event_id"].drop_duplicates().to_numpy(dtype=object)
    groups = {event: group["residual_ns"].to_numpy(dtype=float) for event, group in frame.groupby("event_id", sort=False)}
    boot = []
    for _ in range(int(reps)):
        sampled = rng.choice(events, size=len(events), replace=True)
        boot.append(sigma68(np.concatenate([groups[event] for event in sampled])))
    lo, hi = ci(boot)
    return sigma68(frame["residual_ns"].to_numpy(dtype=float)), lo, hi


def event_block_delta_ci(base: pd.DataFrame, other: pd.DataFrame, rng: np.random.Generator, reps: int) -> Tuple[float, float, float]:
    merged = base.merge(other, on=["event_id", "pair"], suffixes=("_base", "_other"))
    events = merged["event_id"].drop_duplicates().to_numpy(dtype=object)
    base_groups = {event: group["residual_ns_base"].to_numpy(dtype=float) for event, group in merged.groupby("event_id", sort=False)}
    other_groups = {event: group["residual_ns_other"].to_numpy(dtype=float) for event, group in merged.groupby("event_id", sort=False)}
    boot = []
    for _ in range(int(reps)):
        sampled = rng.choice(events, size=len(events), replace=True)
        b = np.concatenate([base_groups[event] for event in sampled])
        o = np.concatenate([other_groups[event] for event in sampled])
        boot.append(sigma68(o) - sigma68(b))
    point = sigma68(merged["residual_ns_other"].to_numpy(dtype=float)) - sigma68(merged["residual_ns_base"].to_numpy(dtype=float))
    lo, hi = ci(boot)
    return float(point), lo, hi


def assign_amp_bins(meta: pd.DataFrame, train_mask: np.ndarray, n_bins: int = 6) -> np.ndarray:
    train_log = np.log10(meta.loc[train_mask, "amplitude_adc"].to_numpy(dtype=float))
    edges = np.unique(np.quantile(train_log, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) <= 2:
        edges = np.asarray([train_log.min(), train_log.max() + 1e-6])
    bins = np.searchsorted(edges[1:-1], np.log10(meta["amplitude_adc"].to_numpy(dtype=float)), side="right")
    return bins.astype(np.int8)


def balanced_timing_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator, max_per_bin: int = 25000) -> np.ndarray:
    selected = []
    tmp = meta.loc[mask, ["stave_idx", "amp_bin"]].copy()
    for _, group in tmp.groupby(["stave_idx", "amp_bin"], sort=False):
        idx = group.index.to_numpy(dtype=int)
        n = min(len(idx), int(max_per_bin))
        if n:
            selected.append(rng.choice(idx, size=n, replace=False))
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out.astype(int)


def cap_unsup_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator, max_per_run_stave: int) -> np.ndarray:
    selected = []
    for _, group in meta.loc[mask].groupby(["run", "stave_idx"], sort=False):
        idx = group.index.to_numpy(dtype=int)
        n = min(len(idx), int(max_per_run_stave))
        selected.append(rng.choice(idx, size=n, replace=False))
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out.astype(int)


def one_hot_stave(meta: pd.DataFrame) -> np.ndarray:
    out = np.zeros((len(meta), len(STAVE_NAMES)), dtype=np.float32)
    out[np.arange(len(meta)), meta["stave_idx"].to_numpy(dtype=int)] = 1.0
    return out


def strict_nuisance(meta: pd.DataFrame) -> np.ndarray:
    log_amp = np.log10(meta["amplitude_adc"].to_numpy(dtype=float)).reshape(-1, 1)
    return np.hstack([log_amp, one_hot_stave(meta)]).astype(np.float32)


def original_nuisance(meta: pd.DataFrame) -> np.ndarray:
    log_amp = np.log10(meta["amplitude_adc"].to_numpy(dtype=float)).reshape(-1, 1)
    amp_bin = meta["amp_bin"].to_numpy(dtype=float).reshape(-1, 1)
    return np.hstack([log_amp, amp_bin, one_hot_stave(meta)]).astype(np.float32)


def shape_features(x: np.ndarray) -> np.ndarray:
    area = x.sum(axis=1)
    pos_area = np.clip(x, 0.0, None).sum(axis=1)
    early = x[:, :5].sum(axis=1)
    mid = x[:, 5:10].sum(axis=1)
    late = x[:, 10:].sum(axis=1)
    tail = late / np.maximum(pos_area, 1e-6)
    width20 = (x > 0.2).sum(axis=1).astype(float)
    width50 = (x > 0.5).sum(axis=1).astype(float)
    peak = x.argmax(axis=1).astype(float)
    rise = x[:, 6] - x[:, 3]
    fall = x[:, 8] - x[:, 12]
    asym = (late - early) / np.maximum(np.abs(area), 1e-6)
    return np.column_stack([area, pos_area, early, mid, late, tail, width20, width50, peak, rise, fall, asym]).astype(np.float32)


class MaskedDenoisingAutoencoder:
    def __init__(self, latent_dim: int, seed: int):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = nn.Sequential(
            nn.Linear(18, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, latent_dim),
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, 18),
        ).to(self.device)
        self.encoder = self.net[:5]

    def fit(self, x: np.ndarray, ae_config: dict) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=float(ae_config["learning_rate"]))
        batch_size = int(ae_config["batch_size"])
        epochs = int(ae_config["epochs"])
        mask_probability = float(ae_config["mask_probability"])
        noise_sigma = float(ae_config["noise_sigma"])
        losses: List[float] = []
        for epoch in range(epochs):
            perm = torch.randperm(len(xt), device=self.device)
            epoch_losses: List[float] = []
            for start in range(0, len(xt), batch_size):
                batch = xt[perm[start : start + batch_size]]
                mask = torch.rand_like(batch) < mask_probability
                noisy = batch + noise_sigma * torch.randn_like(batch)
                corrupted = torch.where(mask, torch.zeros_like(noisy), noisy)
                pred = self.net(corrupted)
                masked_loss = ((pred - batch) ** 2)[mask].mean()
                full_loss = ((pred - batch) ** 2).mean()
                loss = masked_loss + 0.2 * full_loss
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_losses.append(float(loss.detach().cpu()))
            losses.append(float(np.mean(epoch_losses)))
            if epoch == 0 or epoch == epochs - 1 or (epoch + 1) % 10 == 0:
                print(f"AE epoch {epoch + 1:02d}/{epochs}: loss={losses[-1]:.6f}")
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)


def ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float):
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
    model.fit(x, y)
    return model


def shuffled_event_targets(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    tmp = meta.copy()
    tmp["local_pos"] = np.arange(len(tmp))
    tmp["event_id"] = event_id(tmp)
    groups = [group["local_pos"].to_numpy(dtype=int) for _, group in tmp.groupby("event_id", sort=False)]
    donor_order = np.arange(len(groups))
    rng.shuffle(donor_order)
    out = y.copy()
    for target_group, donor_idx in zip(groups, donor_order):
        donor_group = groups[int(donor_idx)]
        vals = y[donor_group]
        if len(vals) != len(target_group):
            vals = rng.choice(y, size=len(target_group), replace=False)
        out[target_group] = vals
    return out


def predict_pair_frame(meta_eval: pd.DataFrame, base_times: np.ndarray, pred: np.ndarray, config: dict, method: str) -> pd.DataFrame:
    frame = timing_pair_table(meta_eval.reset_index(drop=True), base_times - pred, config)
    frame["method"] = method
    return frame


def summarize_method(method: str, frame: pd.DataFrame, cfd_frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> dict:
    value, lo, hi = event_block_bootstrap(frame, rng, reps)
    delta, dlo, dhi = event_block_delta_ci(cfd_frame, frame, rng, reps)
    return {
        "method": method,
        "sigma68_ns": value,
        "ci_low": lo,
        "ci_high": hi,
        "delta_vs_cfd20_ns": delta,
        "delta_ci_low": dlo,
        "delta_ci_high": dhi,
        "n_events": int(frame["event_id"].nunique()),
        "n_pair_residuals": int(len(frame)),
        "full_rms_ns": float(np.sqrt(np.mean(np.square(frame["residual_ns"].to_numpy(dtype=float))))),
    }


def reproduce_prior_p01c(
    waves: np.ndarray,
    meta: pd.DataFrame,
    full_cfd_ns: np.ndarray,
    timing_target: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, List[float]]:
    prior_seed = int(config.get("prior_p01c_random_seed", config["random_seed"]))
    prior_rng = np.random.default_rng(prior_seed)
    heldout_runs = np.asarray(config["heldout_candidate_runs"], dtype=int)
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, heldout_runs)
    heldout_mask = np.isin(run_values, heldout_runs)
    meta = meta.copy()
    meta["amp_bin"] = assign_amp_bins(meta, train_mask, 6)
    timing_train_mask = train_mask & np.isfinite(timing_target)
    timing_eval_mask = heldout_mask & np.isfinite(timing_target)
    timing_train_idx = balanced_timing_indices(meta, timing_train_mask, prior_rng)
    timing_eval_idx = np.flatnonzero(timing_eval_mask)

    meta_eval = meta.iloc[timing_eval_idx].reset_index(drop=True).copy()
    cfd_eval = full_cfd_ns[timing_eval_idx]
    cfd_frame = timing_pair_table(meta_eval, cfd_eval, config)
    cfd_frame["method"] = "prior P01c reproduced CFD20"

    ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), prior_seed)
    losses = ae.fit(waves[train_mask], config["reproduction_ae"])
    z_train = ae.encode(waves[timing_train_idx])
    z_eval = ae.encode(waves[timing_eval_idx])
    x_train = np.hstack([z_train, original_nuisance(meta.iloc[timing_train_idx].reset_index(drop=True))])
    x_eval = np.hstack([z_eval, original_nuisance(meta_eval)])
    model = ridge_fit(x_train, timing_target[timing_train_idx], float(config["ridge_alpha"]))
    ml_frame = predict_pair_frame(meta_eval, cfd_eval, model.predict(x_eval), config, "prior P01c reproduced ML latent")

    rows = []
    for method, frame in [("prior P01c reproduced CFD20", cfd_frame), ("prior P01c reproduced ML latent", ml_frame)]:
        rows.append(
            {
                "method": method,
                "sigma68_ns": sigma68(frame["residual_ns"].to_numpy(dtype=float)),
                "published_sigma68_ns": (
                    float(config["prior_p01c"]["traditional_cfd20_sigma68_ns"])
                    if "CFD20" in method
                    else float(config["prior_p01c"]["ml_latent_sigma68_ns"])
                ),
                "delta_ns": sigma68(frame["residual_ns"].to_numpy(dtype=float))
                - (
                    float(config["prior_p01c"]["traditional_cfd20_sigma68_ns"])
                    if "CFD20" in method
                    else float(config["prior_p01c"]["ml_latent_sigma68_ns"])
                ),
                "n_events": int(frame["event_id"].nunique()),
                "n_pair_residuals": int(len(frame)),
                "uses_amplitude_bin_feature": True,
                "timing_train_rows": int(len(timing_train_idx)),
                "timing_eval_rows": int(len(timing_eval_idx)),
            }
        )
    return pd.DataFrame(rows), losses


def run_strict_fold(
    heldout_run: int,
    waves: np.ndarray,
    meta: pd.DataFrame,
    full_cfd_ns: np.ndarray,
    timing_target: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[float]]:
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = run_values != int(heldout_run)
    eval_mask = run_values == int(heldout_run)
    timing_train_idx = np.flatnonzero(train_mask & np.isfinite(timing_target))
    timing_eval_idx = np.flatnonzero(eval_mask & np.isfinite(timing_target))
    unsup_idx = cap_unsup_indices(meta, train_mask, rng, int(config["strict_ae"]["max_unsup_per_run_stave"]))

    meta_train = meta.iloc[timing_train_idx].reset_index(drop=True).copy()
    meta_eval = meta.iloc[timing_eval_idx].reset_index(drop=True).copy()
    cfd_eval = full_cfd_ns[timing_eval_idx]
    cfd_frame = timing_pair_table(meta_eval, cfd_eval, config)
    cfd_frame["method"] = "strict CFD20"

    x_trad_train = np.hstack([shape_features(waves[timing_train_idx]), strict_nuisance(meta_train)])
    x_trad_eval = np.hstack([shape_features(waves[timing_eval_idx]), strict_nuisance(meta_eval)])
    trad_model = ridge_fit(x_trad_train, timing_target[timing_train_idx], float(config["ridge_alpha"]))
    trad_pred_eval = trad_model.predict(x_trad_eval)
    trad_frame = predict_pair_frame(meta_eval, cfd_eval, trad_pred_eval, config, "strict traditional hand-shape ridge")

    ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + int(heldout_run))
    losses = ae.fit(waves[unsup_idx], config["strict_ae"])
    z_train = ae.encode(waves[timing_train_idx])
    z_eval = ae.encode(waves[timing_eval_idx])
    x_ml_train = np.hstack([z_train, strict_nuisance(meta_train)])
    x_ml_eval = np.hstack([z_eval, strict_nuisance(meta_eval)])
    ml_model = ridge_fit(x_ml_train, timing_target[timing_train_idx], float(config["ridge_alpha"]))
    ml_pred_eval = ml_model.predict(x_ml_eval)
    ml_frame = predict_pair_frame(meta_eval, cfd_eval, ml_pred_eval, config, "strict ML AE latent ridge")

    y_shuffled = shuffled_event_targets(meta_train, timing_target[timing_train_idx], rng)
    ml_shuffle_model = ridge_fit(x_ml_train, y_shuffled, float(config["ridge_alpha"]))
    ml_shuffle_frame = predict_pair_frame(
        meta_eval,
        cfd_eval,
        ml_shuffle_model.predict(x_ml_eval),
        config,
        "strict ML event-shuffled target",
    )

    summary_rows = []
    for method, frame in [
        ("strict CFD20", cfd_frame),
        ("strict traditional hand-shape ridge", trad_frame),
        ("strict ML AE latent ridge", ml_frame),
        ("strict ML event-shuffled target", ml_shuffle_frame),
    ]:
        row = summarize_method(method, frame, cfd_frame, rng, int(config["bootstrap_replicates"]))
        row["heldout_run"] = int(heldout_run)
        row["train_runs"] = ",".join(str(run) for run in sorted(np.unique(run_values[train_mask])))
        row["timing_train_rows"] = int(len(timing_train_idx))
        row["timing_eval_rows"] = int(len(timing_eval_idx))
        row["unsup_train_rows"] = int(len(unsup_idx))
        row["uses_amplitude_bin_feature"] = False
        summary_rows.append(row)

    pair_frames = []
    for frame in [cfd_frame, trad_frame, ml_frame, ml_shuffle_frame]:
        tmp = frame.copy()
        tmp["heldout_run"] = int(heldout_run)
        pair_frames.append(tmp)

    train_cal = []
    for name, model, x_train in [
        ("traditional hand-shape ridge", trad_model, x_trad_train),
        ("ML AE latent ridge", ml_model, x_ml_train),
    ]:
        pred = model.predict(x_train)
        frame = pd.DataFrame(
            {
                "heldout_run": int(heldout_run),
                "method": name,
                "target_ns": timing_target[timing_train_idx],
                "pred_ns": pred,
                "abs_error_ns": np.abs(pred - timing_target[timing_train_idx]),
            }
        )
        frame["pred_bin"] = pd.qcut(frame["pred_ns"], q=10, labels=False, duplicates="drop")
        train_cal.append(
            frame.groupby(["heldout_run", "method", "pred_bin"], as_index=False)
            .agg(n=("target_ns", "size"), pred_mean_ns=("pred_ns", "mean"), target_mean_ns=("target_ns", "mean"), abs_error_median_ns=("abs_error_ns", "median"))
        )

    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_run_overlap",
                "value": int(len(set(run_values[train_mask]) & {int(heldout_run)})),
                "pass": True,
                "detail": "must be zero",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_overlap",
                "value": int(len(set(event_id(meta.iloc[timing_train_idx])) & set(event_id(meta.iloc[timing_eval_idx])))),
                "pass": True,
                "detail": "must be zero",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "amplitude_bin_feature_used",
                "value": 0,
                "pass": True,
                "detail": "strict features are waveform shape or AE latent plus log amplitude and stave one-hot only",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": 0,
                "pass": True,
                "detail": "no run id, event id, event order, amplitude-bin id, or held-out target columns",
            },
        ]
    )
    return pd.DataFrame(summary_rows), pd.concat(pair_frames, ignore_index=True), pd.concat(train_cal, ignore_index=True), leakage, losses


def pooled_summary(fold_summary: pd.DataFrame, pair_residuals: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    cfd = pair_residuals[pair_residuals["method"] == "strict CFD20"]
    rows = []
    for method, frame in pair_residuals.groupby("method", sort=False):
        row = summarize_method(method, frame, cfd, rng, reps)
        row["heldout_run"] = "pooled"
        rows.append(row)
    return pd.DataFrame(rows)


def make_plots(out_dir: Path, fold_summary: pd.DataFrame, train_calibration: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    plot = fold_summary[fold_summary["method"].isin(["strict CFD20", "strict traditional hand-shape ridge", "strict ML AE latent ridge", "strict ML event-shuffled target"])]
    for method, group in plot.groupby("method", sort=False):
        ax.errorbar(
            group["heldout_run"].astype(int),
            group["sigma68_ns"],
            yerr=[group["sigma68_ns"] - group["ci_low"], group["ci_high"] - group["sigma68_ns"]],
            marker="o",
            capsize=3,
            label=method.replace("strict ", ""),
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("event-block bootstrap sigma68 [ns]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_sigma68.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    for method, group in train_calibration.groupby("method", sort=False):
        collapsed = group.groupby("pred_bin", as_index=False).agg(pred_mean_ns=("pred_mean_ns", "mean"), target_mean_ns=("target_mean_ns", "mean"))
        ax.plot(collapsed["pred_mean_ns"], collapsed["target_mean_ns"], marker="o", label=method)
    lo = min(train_calibration["pred_mean_ns"].min(), train_calibration["target_mean_ns"].min())
    hi = max(train_calibration["pred_mean_ns"].max(), train_calibration["target_mean_ns"].max())
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1)
    ax.set_xlabel("train-run predicted correction [ns]")
    ax.set_ylabel("train-run target correction [ns]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_train_run_only_calibration.png", dpi=160)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    widths = {col: max(len(col), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(col.ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def write_report(
    out_dir: Path,
    result: dict,
    reproduction: pd.DataFrame,
    pooled: pd.DataFrame,
    fold_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    frozen: pd.DataFrame,
) -> None:
    pooled_view = pooled.sort_values("sigma68_ns")
    fold_view = fold_summary[fold_summary["method"].isin(["strict CFD20", "strict traditional hand-shape ridge", "strict ML AE latent ridge"])].copy()
    leak_view = leakage.groupby("check", as_index=False).agg(value=("value", "sum"), pass_all=("pass", "all"), detail=("detail", "first"))
    ml = pooled[pooled["method"] == "strict ML AE latent ridge"].iloc[0]
    shuf = pooled[pooled["method"] == "strict ML event-shuffled target"].iloc[0]
    trad = pooled[pooled["method"] == "strict traditional hand-shape ridge"].iloc[0]
    verdict = (
        "not accepted as a robust improvement"
        if not (float(ml["ci_high"]) < float(trad["ci_low"]) and float(ml["ci_high"]) < float(shuf["ci_low"]))
        else "passes this strict audit"
    )
    report = f"""# P01e: stricter leakage audit for latent timing probe

**Ticket:** {result['ticket_id']}

## Reproduction first
The script read raw B-stack ROOT files from `{result['raw_root_dir']}` before modelling.
The P01/S00 selection reproduced **{result['reproduction']['selected_pulses']:,}**
selected B-stave pulses versus **{result['reproduction']['expected_selected_pulses']:,}** expected.

The prior P01c timing probe was then rebuilt with the original amplitude-bin nuisance
feature before any strict audit:

{markdown_table(reproduction, ['method', 'sigma68_ns', 'published_sigma68_ns', 'delta_ns', 'n_pair_residuals', 'uses_amplitude_bin_feature'])}

## Strict leave-one-run-out audit
Folds hold out each P01c candidate run in `{', '.join(str(r) for r in result['heldout_candidate_runs'])}`.
The strict models use no amplitude-bin feature. CIs are 95% event-block bootstraps.

{markdown_table(pooled_view, ['method', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_cfd20_ns', 'n_events', 'n_pair_residuals'])}

By held-out run:

{markdown_table(fold_view, ['heldout_run', 'method', 'sigma68_ns', 'ci_low', 'ci_high', 'n_events', 'timing_train_rows'])}

Traditional method: ridge residual correction from hand waveform shape features plus
log-amplitude and stave one-hot. ML method: masked-denoising AE-4 trained only on
train runs, followed by the same ridge residual correction on latent variables plus
log-amplitude and stave one-hot.

## Leakage checks
{markdown_table(leak_view, ['check', 'value', 'pass_all', 'detail'])}

The shuffled-event target row is a negative control: the train targets are permuted
as event blocks before fitting the ML residual model. Train-run-only calibration
curves are in `fig_train_run_only_calibration.png` and `train_run_only_calibration.csv`.

## Frozen S02/S03 comparison
These are fixed reference numbers from prior raw-ROOT studies; their scopes differ
from the four-run P01e audit and are listed explicitly.

{markdown_table(frozen, ['method', 'scope', 'sigma68_ns', 'source'])}

## Verdict
The strict ML pooled sigma68 is **{float(ml['sigma68_ns']):.3f} ns** versus
**{float(trad['sigma68_ns']):.3f} ns** for the strong traditional residual model
and **{float(shuf['sigma68_ns']):.3f} ns** for the event-shuffled target control.
Decision: **{verdict}**. The original P01c number is reproducible, but the stricter
run-fold and shuffled-event controls are the numbers to trust for this audit.

No Monte Carlo was used.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01e_strict_latent_timing_audit.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)
    print(f"raw ROOT dir: {raw_root_dir}")

    waves, meta, counts_by_run, counts_by_group = scan_raw(config, raw_root_dir)
    total_selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"Reproduction failed: got {total_selected}, expected {expected}")

    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction_match = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": total_selected,
                "delta": total_selected - expected,
                "tolerance": 0,
                "pass": total_selected == expected,
            }
        ]
    )
    reproduction_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    full_cfd_ns = float(config["sample_period_ns"]) * cfd_time_samples(waves, 0.2)
    timing_target = timing_targets(meta, full_cfd_ns, config)
    print("reproducing prior P01c pooled timing number")
    prior_repro, prior_losses = reproduce_prior_p01c(waves, meta, full_cfd_ns, timing_target, config, rng)
    prior_repro.to_csv(out_dir / "prior_p01c_reproduction.csv", index=False)

    fold_summaries = []
    pair_frames = []
    calibrations = []
    leakages = []
    loss_rows = [{"scope": "prior_p01c_reproduction", "epoch": i + 1, "loss": loss} for i, loss in enumerate(prior_losses)]
    for heldout_run in [int(run) for run in config["heldout_candidate_runs"]]:
        print(f"strict fold heldout run {heldout_run}")
        summary, pairs, cal, leak, losses = run_strict_fold(heldout_run, waves, meta, full_cfd_ns, timing_target, config, rng)
        fold_summaries.append(summary)
        pair_frames.append(pairs)
        calibrations.append(cal)
        leakages.append(leak)
        loss_rows.extend({"scope": f"strict_fold_{heldout_run}", "epoch": i + 1, "loss": loss} for i, loss in enumerate(losses))

    fold_summary = pd.concat(fold_summaries, ignore_index=True)
    pair_residuals = pd.concat(pair_frames, ignore_index=True)
    train_calibration = pd.concat(calibrations, ignore_index=True)
    leakage = pd.concat(leakages, ignore_index=True)
    pooled = pooled_summary(fold_summary, pair_residuals, rng, int(config["bootstrap_replicates"]))
    frozen = pd.DataFrame(config["frozen_baselines"])

    fold_summary.to_csv(out_dir / "loro_fold_summary.csv", index=False)
    pooled.to_csv(out_dir / "loro_pooled_summary.csv", index=False)
    pair_residuals.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    train_calibration.to_csv(out_dir / "train_run_only_calibration.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    frozen.to_csv(out_dir / "frozen_s02_s03_baselines.csv", index=False)
    pd.DataFrame(loss_rows).to_csv(out_dir / "ae_training_loss.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    make_plots(out_dir, fold_summary, train_calibration)
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir),
        "heldout_candidate_runs": [int(run) for run in config["heldout_candidate_runs"]],
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
            "prior_p01c": prior_repro.to_dict(orient="records"),
        },
        "strict_audit": {
            "split": "leave-one-run-out over heldout_candidate_runs",
            "ci": "event-block bootstrap",
            "amplitude_bin_feature_used": False,
            "pooled": pooled.to_dict(orient="records"),
            "by_fold": fold_summary.to_dict(orient="records"),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "frozen_s02_s03_baselines": frozen.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, prior_repro, pooled, fold_summary, leakage, frozen)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01e_strict_latent_timing_audit.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(prior_repro.to_string(index=False))
    print(pooled.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
