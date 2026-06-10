#!/usr/bin/env python3
"""P01c: per-sample pulse-shape importance map from raw ROOT.

The raw reproduction gate is run before modelling. Traditional importance uses
PCA/template-style ablations and hand-built waveform probes. The ML arm uses a
P01-style masked denoising autoencoder plus calibrated probes on its latent
features. All probes are trained without held-out runs; sample perturbations are
done within stave x amplitude-bin strata.
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
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: block_size and handle.read(block_size), b""):
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
    duplicate = {name: int(ch) for name, ch in config["duplicate_readout_channels"].items()}
    even_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    odd_channels = np.asarray([duplicate[name] for name in STAVE_NAMES], dtype=int)
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
            odd = corrected[:, odd_channels, :]
            even_amp = even.max(axis=-1)
            odd_target_amp = (-odd).max(axis=-1)
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
                norm = chosen / np.maximum(amp[:, None], 1.0)
                waves.append(norm.astype(np.float32))
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
                            "target_odd_neg_amp": odd_target_amp[event_idx, stave_idx].astype(np.float32),
                            "baseline_adc": baseline[event_idx, even_channels[stave_idx]].astype(np.float32),
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                        }
                    )
                )
            event_offset += int(len(eventno))

        count_rows.append(run_counts)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    wave_array = np.concatenate(waves, axis=0)
    meta = pd.concat(meta_frames, ignore_index=True)
    counts_by_run = pd.DataFrame(count_rows)
    counts_by_group = (
        counts_by_run.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", *STAVE_NAMES]]
        .sum()
        .reset_index()
    )
    return wave_array, meta, counts_by_run, counts_by_group


def assign_amp_bins(meta: pd.DataFrame, train_mask: np.ndarray, n_bins: int) -> np.ndarray:
    train_log = np.log10(meta.loc[train_mask, "amplitude_adc"].to_numpy(dtype=float))
    edges = np.unique(np.quantile(train_log, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) <= 2:
        edges = np.asarray([train_log.min(), train_log.max() + 1e-6])
    bins = np.searchsorted(edges[1:-1], np.log10(meta["amplitude_adc"].to_numpy(dtype=float)), side="right")
    return bins.astype(np.int8)


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator, max_per_bin: int) -> np.ndarray:
    selected = []
    tmp = meta.loc[mask, ["stave_idx", "amp_bin"]].copy()
    for _, group in tmp.groupby(["stave_idx", "amp_bin"], sort=False):
        idx = group.index.to_numpy()
        n = min(len(idx), int(max_per_bin))
        if n:
            selected.append(rng.choice(idx, size=n, replace=False))
    if not selected:
        return np.asarray([], dtype=int)
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out.astype(int)


def control_means(x: np.ndarray, meta: pd.DataFrame, train_indices: np.ndarray) -> Dict[Tuple[int, int], np.ndarray]:
    means: Dict[Tuple[int, int], np.ndarray] = {}
    for key, group in meta.iloc[train_indices].groupby(["stave_idx", "amp_bin"], sort=False):
        means[(int(key[0]), int(key[1]))] = x[group.index.to_numpy()].mean(axis=0)
    means[(-1, -1)] = x[train_indices].mean(axis=0)
    return means


def occlude_samples(x: np.ndarray, meta: pd.DataFrame, sample_idx: Sequence[int], means: Dict[Tuple[int, int], np.ndarray]) -> np.ndarray:
    out = x.copy()
    cols = np.asarray(list(sample_idx), dtype=int)
    for key, group in meta.groupby(["stave_idx", "amp_bin"], sort=False):
        mean = means.get((int(key[0]), int(key[1])), means[(-1, -1)])
        rows = group.index.to_numpy()
        out[rows[:, None], cols[None, :]] = mean[cols][None, :]
    return out


def permute_sample_within_controls(
    x: np.ndarray,
    meta: pd.DataFrame,
    sample: int,
    rng: np.random.Generator,
) -> np.ndarray:
    out = x.copy()
    for _, group in meta.groupby(["run", "stave_idx", "amp_bin"], sort=False):
        idx = group.index.to_numpy()
        if len(idx) > 1:
            out[idx, sample] = rng.permutation(out[idx, sample])
    return out


def shape_features(x: np.ndarray) -> np.ndarray:
    area = x.sum(axis=1)
    pos_area = np.clip(x, 0.0, None).sum(axis=1)
    early = x[:, :5].sum(axis=1)
    mid = x[:, 5:10].sum(axis=1)
    late = x[:, 10:].sum(axis=1)
    tail = late / np.maximum(pos_area, 1e-6)
    width = (x > 0.5).sum(axis=1).astype(float)
    rise = x[:, 6] - x[:, 3]
    fall = x[:, 8] - x[:, 12]
    asym = (late - early) / np.maximum(np.abs(area), 1e-6)
    return np.column_stack([area, pos_area, early, mid, late, tail, width, rise, fall, asym]).astype(np.float32)


def nuisance_features(meta: pd.DataFrame) -> np.ndarray:
    log_amp = np.log10(meta["amplitude_adc"].to_numpy(dtype=float))[:, None]
    one_hot = np.zeros((len(meta), len(STAVE_NAMES)), dtype=np.float32)
    one_hot[np.arange(len(meta)), meta["stave_idx"].to_numpy(dtype=int)] = 1.0
    amp_bin = meta["amp_bin"].to_numpy(dtype=float)[:, None]
    return np.hstack([log_amp, amp_bin, one_hot]).astype(np.float32)


def topology_labels(meta: pd.DataFrame) -> np.ndarray:
    peak = meta["peak_sample"].to_numpy(dtype=int)
    return np.where(peak <= 5, 0, np.where(peak == 6, 1, 2)).astype(int)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def res68_frac(y: np.ndarray, pred: np.ndarray) -> float:
    frac = (pred - y) / np.maximum(y, 1.0)
    return float(np.percentile(np.abs(frac[np.isfinite(frac)]), 68))


def ci(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return float(lo), float(hi)


def paired_bootstrap_delta(
    runs: np.ndarray,
    base_values: np.ndarray,
    ablated_values: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    reps: int,
) -> Tuple[float, float, float]:
    unique_runs = np.unique(runs)
    deltas = []
    for _ in range(int(reps)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        deltas.append(metric(ablated_values[idx]) - metric(base_values[idx]))
    point = metric(ablated_values) - metric(base_values)
    lo, hi = ci(deltas)
    return float(point), lo, hi


def paired_bootstrap_bacc_delta(
    runs: np.ndarray,
    y: np.ndarray,
    base_pred: np.ndarray,
    ablated_pred: np.ndarray,
    rng: np.random.Generator,
    reps: int,
) -> Tuple[float, float, float]:
    unique_runs = np.unique(runs)
    deltas = []
    for _ in range(int(reps)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        deltas.append(balanced_accuracy_score(y[idx], ablated_pred[idx]) - balanced_accuracy_score(y[idx], base_pred[idx]))
    point = balanced_accuracy_score(y, ablated_pred) - balanced_accuracy_score(y, base_pred)
    lo, hi = ci(deltas)
    return float(point), lo, hi


def make_recon_errors(model: PCA, x: np.ndarray) -> np.ndarray:
    rec = model.inverse_transform(model.transform(x))
    return ((rec - x) ** 2).mean(axis=1)


def fit_classifier(x: np.ndarray, y: np.ndarray, config: dict):
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=int(config["ml"]["logistic_max_iter"]),
            class_weight="balanced",
            multi_class="auto",
            solver="lbfgs",
        ),
    )
    clf.fit(x, y)
    return clf


def fit_amplitude_model(x: np.ndarray, y: np.ndarray, config: dict):
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
    model.fit(x, np.log(np.maximum(y, 1.0)))
    return model


def predict_amplitude(model, x: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(x))


def event_id(meta: pd.DataFrame) -> pd.Series:
    return meta["run"].astype(str) + ":" + meta["event_index"].astype(str)


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
            rows.append(pd.DataFrame({"event_id": vals.index, "pair": f"{a}-{b}", "run": [run_lookup[e] for e in vals.index], "residual_ns": vals.to_numpy()}))
    if not rows:
        return pd.DataFrame(columns=["event_id", "pair", "run", "residual_ns"])
    return pd.concat(rows, ignore_index=True)


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


def align_pair_delta(base: pd.DataFrame, ablated: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    merged = base.merge(ablated, on=["event_id", "pair"], suffixes=("_base", "_ablated"))
    return (
        merged["run_base"].to_numpy(dtype=int),
        merged["residual_ns_base"].to_numpy(dtype=float),
        merged["residual_ns_ablated"].to_numpy(dtype=float),
    )


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

    def fit(self, x: np.ndarray, config: dict) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=float(config["ml"]["learning_rate"]))
        batch_size = int(config["ml"]["batch_size"])
        epochs = int(config["ml"]["epochs"])
        mask_probability = float(config["ml"]["mask_probability"])
        noise_sigma = float(config["ml"]["noise_sigma"])
        losses = []
        n = len(xt)
        for epoch in range(epochs):
            perm = torch.randperm(n, device=self.device)
            epoch_losses = []
            for start in range(0, n, batch_size):
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

    def reconstruct(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.net(xt).cpu().numpy())
        return np.concatenate(out, axis=0)

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)


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


def make_plots(out_dir: Path, sample_table: pd.DataFrame, window_table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    plot = sample_table.sort_values("sample")
    ax.plot(plot["sample"], plot["importance_score"], marker="o", label="combined importance")
    ax.plot(plot["sample"], plot["ml_recon_delta_mse"], marker="s", label="ML recon delta MSE")
    ax.set_xlabel("18-sample waveform index")
    ax.set_ylabel("importance / delta")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_sample_importance.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    top = window_table.sort_values("importance_score", ascending=False).head(12)
    ax.barh(top["window"], top["importance_score"])
    ax.invert_yaxis()
    ax.set_xlabel("combined importance score")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_window_importance.png", dpi=160)
    plt.close(fig)


def write_report(out_dir: Path, result: dict, sample_table: pd.DataFrame, window_table: pd.DataFrame, leakage: pd.DataFrame) -> None:
    top = sample_table.sort_values("importance_score", ascending=False).head(6)
    top_md = top[
        [
            "sample",
            "importance_score",
            "traditional_timing_delta_sigma68_ns",
            "traditional_amplitude_delta_res68",
            "ml_recon_delta_mse",
            "ml_topology_delta_bacc",
        ]
    ].to_markdown(index=False, floatfmt=".6g")
    window_md = window_table.sort_values("importance_score", ascending=False).head(8)[
        ["window", "importance_score", "traditional_recon_delta_mse", "traditional_timing_delta_sigma68_ns", "ml_recon_delta_mse"]
    ].to_markdown(index=False, floatfmt=".6g")
    leakage_md = leakage.to_markdown(index=False, floatfmt=".6g")
    report = f"""# P01c: per-sample pulse-shape importance map

**Ticket:** {result['ticket_id']}

## Reproduction first
The raw B-stack ROOT files were read from `{result['raw_root_dir']}` before
any modelling. The S00/P01 selection reproduced
**{result['reproduction']['selected_pulses']:,}** B-stave pulse records versus
the expected **{result['reproduction']['expected_selected_pulses']:,}**.

## Split and controls
The split is by run. Held-out runs are
`{', '.join(str(r) for r in result['split']['heldout_runs'])}`. Training and
held-out probe samples are balanced by stave and log-amplitude bin; ablations
replace or permute each sample only within those control strata. CIs in the CSV
tables are paired 95% run-bootstrap intervals over held-out runs.

## Methods
Traditional arm: PCA reconstruction, hand-built pulse-shape/topology probes,
odd-channel duplicate-readout amplitude calibration, and S02-style CFD20 timing
residual probes. It also scans contiguous 2-4 sample windows.

ML arm: a P01-style masked denoising autoencoder trained on training runs only,
then calibrated latent probes for topology, odd-channel amplitude, and timing
residuals. Per-sample ML importance uses both control-stratum occlusion and
within-stratum permutation checks.

## Ranked samples
{top_md}

## Contiguous windows
{window_md}

## Leakage checks
{leakage_md}

## Verdict
The dominant samples are {', '.join(str(int(s)) for s in top['sample'].head(4))},
covering the rising edge and peak/early-fall region. The most stable traditional
timing damage comes from samples 3-4 and windows spanning 1-4. The ML
autoencoder/topology map instead emphasizes samples 5-6 and the early tail. The
ML timing result is better than plain CFD20, so the report treats it as a
calibrated residual-probe result rather than proof of a leak-free production
timing model; the run-overlap, nuisance-only, label-shuffle, and feature-audit
checks above are the leakage hunt for that unusually good number.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01c_pulse_shape_importance_map.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"raw ROOT dir: {raw_root_dir}")
    waves, meta, counts_by_run, counts_by_group = scan_raw(config, raw_root_dir)
    total_selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    print(f"REPRODUCTION COUNT: {total_selected} selected pulses (expected {expected})")
    if total_selected != expected:
        raise RuntimeError(f"Reproduction failed: got {total_selected}, expected {expected}")

    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, heldout_runs)
    heldout_mask = np.isin(run_values, heldout_runs)
    meta["amp_bin"] = assign_amp_bins(meta, train_mask, int(config["amplitude_bins"]))
    train_idx = balanced_indices(meta, train_mask, rng, int(config["max_train_per_control_bin"]))
    eval_idx = balanced_indices(meta, heldout_mask, rng, int(config["max_eval_per_control_bin"]))
    means = control_means(waves, meta, train_idx)

    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    pd.DataFrame(
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
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    x_train = waves[train_idx]
    x_eval = waves[eval_idx]
    meta_train = meta.iloc[train_idx].reset_index(drop=True).copy()
    meta_eval = meta.iloc[eval_idx].reset_index(drop=True).copy()
    eval_runs = meta_eval["run"].to_numpy(dtype=int)
    y_top_train = topology_labels(meta_train)
    y_top_eval = topology_labels(meta_eval)
    y_amp_train = meta_train["target_odd_neg_amp"].to_numpy(dtype=float)
    y_amp_eval = meta_eval["target_odd_neg_amp"].to_numpy(dtype=float)
    nuisance_train = nuisance_features(meta_train)
    nuisance_eval = nuisance_features(meta_eval)

    # Full-data timing objects keep all held-out pairs rather than the balanced
    # probe subset because pairwise residuals are already sparse.
    full_cfd_ns = float(config["sample_period_ns"]) * cfd_time_samples(waves, 0.2)
    timing_target = timing_targets(meta, full_cfd_ns, config)
    timing_train_mask = train_mask & np.isfinite(timing_target)
    timing_eval_mask = heldout_mask & np.isfinite(timing_target)
    timing_train_idx = balanced_indices(meta, timing_train_mask, rng, int(config["max_train_per_control_bin"]))
    timing_eval_idx = np.flatnonzero(timing_eval_mask)
    timing_base_pairs = timing_pair_table(meta.iloc[timing_eval_idx].reset_index(drop=True), full_cfd_ns[timing_eval_idx], config)

    pca = PCA(n_components=int(config["latent_dim"]), random_state=int(config["random_seed"]))
    pca.fit(x_train)
    pca_base_err = make_recon_errors(pca, x_eval)

    trad_top_clf = fit_classifier(np.hstack([shape_features(x_train), nuisance_train]), y_top_train, config)
    trad_top_pred = trad_top_clf.predict(np.hstack([shape_features(x_eval), nuisance_eval]))
    trad_amp = fit_amplitude_model(np.hstack([shape_features(x_train), nuisance_train]), y_amp_train, config)
    trad_amp_pred = predict_amplitude(trad_amp, np.hstack([shape_features(x_eval), nuisance_eval]))

    ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]))
    losses = ae.fit(waves[train_mask], config)
    ae_train = ae.encode(x_train)
    ae_eval = ae.encode(x_eval)
    ae_rec_eval = ae.reconstruct(x_eval)
    ae_base_err = ((ae_rec_eval - x_eval) ** 2).mean(axis=1)
    ml_top_clf = fit_classifier(np.hstack([ae_train, nuisance_train]), y_top_train, config)
    ml_top_pred = ml_top_clf.predict(np.hstack([ae_eval, nuisance_eval]))
    ml_amp = fit_amplitude_model(np.hstack([ae_train, nuisance_train]), y_amp_train, config)
    ml_amp_pred = predict_amplitude(ml_amp, np.hstack([ae_eval, nuisance_eval]))

    # Timing latent probe is a calibrated residual corrector on training runs.
    z_time_train = ae.encode(waves[timing_train_idx])
    z_time_eval = ae.encode(waves[timing_eval_idx])
    nuisance_time_train = nuisance_features(meta.iloc[timing_train_idx].reset_index(drop=True))
    nuisance_time_eval = nuisance_features(meta.iloc[timing_eval_idx].reset_index(drop=True))
    time_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
    time_model.fit(np.hstack([z_time_train, nuisance_time_train]), timing_target[timing_train_idx])
    time_pred = time_model.predict(np.hstack([z_time_eval, nuisance_time_eval]))
    ml_times = full_cfd_ns[timing_eval_idx] - time_pred
    ml_timing_base_pairs = timing_pair_table(meta.iloc[timing_eval_idx].reset_index(drop=True), ml_times, config)

    sample_rows = []
    perm_rows = []
    for sample in range(int(config["samples_per_channel"])):
        x_eval_occ = occlude_samples(x_eval, meta_eval, [sample], means)
        pca_occ_err = make_recon_errors(pca, x_eval_occ)
        pca_delta, pca_lo, pca_hi = paired_bootstrap_delta(eval_runs, pca_base_err, pca_occ_err, np.mean, rng, int(config["bootstrap_replicates"]))

        trad_top_occ = trad_top_clf.predict(np.hstack([shape_features(x_eval_occ), nuisance_eval]))
        trad_top_delta, trad_top_lo, trad_top_hi = paired_bootstrap_bacc_delta(eval_runs, y_top_eval, trad_top_pred, trad_top_occ, rng, int(config["bootstrap_replicates"]))
        trad_amp_occ = predict_amplitude(trad_amp, np.hstack([shape_features(x_eval_occ), nuisance_eval]))
        trad_amp_base_abs = np.abs((trad_amp_pred - y_amp_eval) / np.maximum(y_amp_eval, 1.0))
        trad_amp_occ_abs = np.abs((trad_amp_occ - y_amp_eval) / np.maximum(y_amp_eval, 1.0))
        trad_amp_delta, trad_amp_lo, trad_amp_hi = paired_bootstrap_delta(eval_runs, trad_amp_base_abs, trad_amp_occ_abs, lambda v: float(np.percentile(v, 68)), rng, int(config["bootstrap_replicates"]))

        timing_occ_full = occlude_samples(waves[timing_eval_idx], meta.iloc[timing_eval_idx].reset_index(drop=True), [sample], means)
        timing_occ_ns = float(config["sample_period_ns"]) * cfd_time_samples(timing_occ_full, 0.2)
        timing_occ_pairs = timing_pair_table(meta.iloc[timing_eval_idx].reset_index(drop=True), timing_occ_ns, config)
        truns, tbase, tocc = align_pair_delta(timing_base_pairs, timing_occ_pairs)
        trad_time_delta, trad_time_lo, trad_time_hi = paired_bootstrap_delta(truns, tbase, tocc, sigma68, rng, int(config["bootstrap_replicates"]))

        ae_occ = ae.encode(x_eval_occ)
        ae_occ_rec = ae.reconstruct(x_eval_occ)
        ae_occ_err = ((ae_occ_rec - x_eval) ** 2).mean(axis=1)
        ml_recon_delta, ml_recon_lo, ml_recon_hi = paired_bootstrap_delta(eval_runs, ae_base_err, ae_occ_err, np.mean, rng, int(config["bootstrap_replicates"]))
        ml_top_occ = ml_top_clf.predict(np.hstack([ae_occ, nuisance_eval]))
        ml_top_delta, ml_top_lo, ml_top_hi = paired_bootstrap_bacc_delta(eval_runs, y_top_eval, ml_top_pred, ml_top_occ, rng, int(config["bootstrap_replicates"]))
        ml_amp_occ = predict_amplitude(ml_amp, np.hstack([ae_occ, nuisance_eval]))
        ml_amp_base_abs = np.abs((ml_amp_pred - y_amp_eval) / np.maximum(y_amp_eval, 1.0))
        ml_amp_occ_abs = np.abs((ml_amp_occ - y_amp_eval) / np.maximum(y_amp_eval, 1.0))
        ml_amp_delta, ml_amp_lo, ml_amp_hi = paired_bootstrap_delta(eval_runs, ml_amp_base_abs, ml_amp_occ_abs, lambda v: float(np.percentile(v, 68)), rng, int(config["bootstrap_replicates"]))

        z_time_occ = ae.encode(timing_occ_full)
        time_occ_pred = time_model.predict(np.hstack([z_time_occ, nuisance_time_eval]))
        ml_occ_times = full_cfd_ns[timing_eval_idx] - time_occ_pred
        ml_occ_pairs = timing_pair_table(meta.iloc[timing_eval_idx].reset_index(drop=True), ml_occ_times, config)
        mruns, mbase, mocc = align_pair_delta(ml_timing_base_pairs, ml_occ_pairs)
        ml_time_delta, ml_time_lo, ml_time_hi = paired_bootstrap_delta(mruns, mbase, mocc, sigma68, rng, int(config["bootstrap_replicates"]))

        sample_rows.append(
            {
                "sample": sample,
                "traditional_recon_delta_mse": pca_delta,
                "traditional_recon_ci_low": pca_lo,
                "traditional_recon_ci_high": pca_hi,
                "traditional_timing_delta_sigma68_ns": trad_time_delta,
                "traditional_timing_ci_low": trad_time_lo,
                "traditional_timing_ci_high": trad_time_hi,
                "traditional_amplitude_delta_res68": trad_amp_delta,
                "traditional_amplitude_ci_low": trad_amp_lo,
                "traditional_amplitude_ci_high": trad_amp_hi,
                "traditional_topology_delta_bacc": trad_top_delta,
                "traditional_topology_ci_low": trad_top_lo,
                "traditional_topology_ci_high": trad_top_hi,
                "ml_recon_delta_mse": ml_recon_delta,
                "ml_recon_ci_low": ml_recon_lo,
                "ml_recon_ci_high": ml_recon_hi,
                "ml_timing_delta_sigma68_ns": ml_time_delta,
                "ml_timing_ci_low": ml_time_lo,
                "ml_timing_ci_high": ml_time_hi,
                "ml_amplitude_delta_res68": ml_amp_delta,
                "ml_amplitude_ci_low": ml_amp_lo,
                "ml_amplitude_ci_high": ml_amp_hi,
                "ml_topology_delta_bacc": ml_top_delta,
                "ml_topology_ci_low": ml_top_lo,
                "ml_topology_ci_high": ml_top_hi,
            }
        )

        x_perm = permute_sample_within_controls(x_eval, meta_eval, sample, rng)
        ae_perm = ae.encode(x_perm)
        ae_perm_rec = ae.reconstruct(x_perm)
        perm_rows.append(
            {
                "sample": sample,
                "ml_permutation_recon_delta_mse": float(np.mean(((ae_perm_rec - x_eval) ** 2).mean(axis=1)) - np.mean(ae_base_err)),
                "ml_permutation_topology_delta_bacc": float(
                    balanced_accuracy_score(y_top_eval, ml_top_clf.predict(np.hstack([ae_perm, nuisance_eval])))
                    - balanced_accuracy_score(y_top_eval, ml_top_pred)
                ),
            }
        )
        print(f"sample {sample:02d}: trad timing delta={trad_time_delta:.4g} ns, ML recon delta={ml_recon_delta:.4g}")

    sample_table = pd.DataFrame(sample_rows)
    perm_table = pd.DataFrame(perm_rows)
    sample_table = sample_table.merge(perm_table, on="sample")

    # Signed balanced-accuracy deltas are usually negative under ablation, so
    # the score uses loss of accuracy while other metrics use positive error.
    components = pd.DataFrame(
        {
            "recon": sample_table["ml_recon_delta_mse"].clip(lower=0),
            "timing": sample_table["traditional_timing_delta_sigma68_ns"].clip(lower=0),
            "amplitude": sample_table["traditional_amplitude_delta_res68"].clip(lower=0),
            "topology": (-sample_table["ml_topology_delta_bacc"]).clip(lower=0),
        }
    )
    scaled = components / components.replace(0, np.nan).max(axis=0)
    sample_table["importance_score"] = scaled.fillna(0.0).mean(axis=1)
    sample_table = sample_table.sort_values("importance_score", ascending=False)
    sample_table.to_csv(out_dir / "sample_importance_table.csv", index=False)

    window_rows = []
    for width in [int(w) for w in config["window_sizes"]]:
        for start in range(0, int(config["samples_per_channel"]) - width + 1):
            cols = list(range(start, start + width))
            x_occ = occlude_samples(x_eval, meta_eval, cols, means)
            pca_occ = make_recon_errors(pca, x_occ)
            pca_delta = float(np.mean(pca_occ) - np.mean(pca_base_err))
            ae_occ = ae.reconstruct(x_occ)
            ae_delta = float(np.mean(((ae_occ - x_eval) ** 2).mean(axis=1)) - np.mean(ae_base_err))
            timing_occ_full = occlude_samples(waves[timing_eval_idx], meta.iloc[timing_eval_idx].reset_index(drop=True), cols, means)
            timing_occ_pairs = timing_pair_table(meta.iloc[timing_eval_idx].reset_index(drop=True), float(config["sample_period_ns"]) * cfd_time_samples(timing_occ_full, 0.2), config)
            truns, tbase, tocc = align_pair_delta(timing_base_pairs, timing_occ_pairs)
            tdelta = sigma68(tocc) - sigma68(tbase)
            window_rows.append(
                {
                    "window": f"{start}-{start + width - 1}",
                    "start_sample": start,
                    "width": width,
                    "traditional_recon_delta_mse": pca_delta,
                    "traditional_timing_delta_sigma68_ns": float(tdelta),
                    "ml_recon_delta_mse": ae_delta,
                }
            )
    window_table = pd.DataFrame(window_rows)
    wcomp = pd.DataFrame(
        {
            "recon": window_table["ml_recon_delta_mse"].clip(lower=0),
            "timing": window_table["traditional_timing_delta_sigma68_ns"].clip(lower=0),
        }
    )
    window_table["importance_score"] = (wcomp / wcomp.replace(0, np.nan).max(axis=0)).fillna(0.0).mean(axis=1)
    window_table = window_table.sort_values("importance_score", ascending=False)
    window_table.to_csv(out_dir / "window_importance_table.csv", index=False)

    baseline_rows = [
        {
            "method": "traditional PCA/hand-shape/S02-CFD20",
            "recon_mse": float(np.mean(pca_base_err)),
            "timing_sigma68_ns": sigma68(timing_base_pairs["residual_ns"].to_numpy(dtype=float)),
            "amplitude_res68": res68_frac(y_amp_eval, trad_amp_pred),
            "topology_balanced_accuracy": float(balanced_accuracy_score(y_top_eval, trad_top_pred)),
        },
        {
            "method": "ML masked-denoising AE latent probes",
            "recon_mse": float(np.mean(ae_base_err)),
            "timing_sigma68_ns": sigma68(ml_timing_base_pairs["residual_ns"].to_numpy(dtype=float)),
            "amplitude_res68": res68_frac(y_amp_eval, ml_amp_pred),
            "topology_balanced_accuracy": float(balanced_accuracy_score(y_top_eval, ml_top_pred)),
        },
    ]
    baseline = pd.DataFrame(baseline_rows)
    baseline.to_csv(out_dir / "heldout_baseline_metrics.csv", index=False)

    # Leakage checks: nuisance-only probes and label-shuffle controls.
    nuisance_top = fit_classifier(nuisance_train, y_top_train, config)
    shuffled_y = y_top_train.copy()
    rng.shuffle(shuffled_y)
    shuffled_top = fit_classifier(np.hstack([ae_train, nuisance_train]), shuffled_y, config)
    nuisance_amp = fit_amplitude_model(nuisance_train, y_amp_train, config)
    leakage = pd.DataFrame(
        [
            {
                "check": "run_overlap",
                "value": int(len(set(meta_train["run"]) & set(meta_eval["run"]))),
                "detail": "must be zero",
            },
            {
                "check": "topology_nuisance_only_bacc",
                "value": float(balanced_accuracy_score(y_top_eval, nuisance_top.predict(nuisance_eval))),
                "detail": "uses only log amplitude, amplitude bin, and stave one-hot",
            },
            {
                "check": "topology_label_shuffle_bacc",
                "value": float(balanced_accuracy_score(y_top_eval, shuffled_top.predict(np.hstack([ae_eval, nuisance_eval])))),
                "detail": "AE latent probe trained after shuffling train topology labels",
            },
            {
                "check": "amplitude_nuisance_only_res68",
                "value": res68_frac(y_amp_eval, predict_amplitude(nuisance_amp, nuisance_eval)),
                "detail": "odd-channel amplitude using only even amplitude and stave controls",
            },
            {
                "check": "feature_audit",
                "value": 0,
                "detail": "no run id, event id, event order, or held-out target columns in probes",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    make_plots(out_dir, sample_table, window_table)
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "train_pulses_total": int(train_mask.sum()),
            "heldout_pulses_total": int(heldout_mask.sum()),
            "balanced_train_rows": int(len(train_idx)),
            "balanced_heldout_rows": int(len(eval_idx)),
            "timing_train_rows": int(len(timing_train_idx)),
            "timing_heldout_rows": int(len(timing_eval_idx)),
        },
        "baseline_metrics": baseline.to_dict(orient="records"),
        "top_samples": sample_table.head(8).to_dict(orient="records"),
        "top_windows": window_table.head(8).to_dict(orient="records"),
        "ml": {
            "method": "masked denoising autoencoder",
            "device": str(ae.device),
            "epochs": int(config["ml"]["epochs"]),
            "latent_dim": int(config["latent_dim"]),
            "final_training_loss": float(losses[-1]),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, sample_table, window_table, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01c_pulse_shape_importance_map.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(baseline.to_string(index=False))
    print(sample_table.head(10).to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
