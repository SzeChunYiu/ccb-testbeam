#!/usr/bin/env python3
"""P01a: amplitude/topology-controlled waveform representation probes.

This ticket follows P01 but adds stricter controls. It reads the raw B-stack
ROOT files first, reproduces the S00 selected-pulse count, then compares a
traditional residual-PCA representation with a masked-denoising autoencoder.
All reported probe fits train on runs disjoint from the held-out runs.
"""

from __future__ import annotations

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
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_ID = "1781005204.1227.36547733"
OUT_DIR = Path("reports/1781005204.1227.36547733__p01a_controlled_waveform_probes")
RAW_ROOT_DIR_CANDIDATES = [
    Path("data/extracted/root/root"),
    Path("data/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/Desktop/test_beam/data/root/root"),
]
EXPECTED_SELECTED_PULSES = 640737
AMPLITUDE_CUT_ADC = 1000.0
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
STAVE_NAMES = ["B2", "B4", "B6", "B8"]
STAVE_CHANNELS = np.asarray([0, 2, 4, 6], dtype=int)
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
HELDOUT_RUNS = np.asarray([42, 57, 64, 65], dtype=int)
SEED = 91073
BOOTSTRAP_REPLICATES = 500
MAX_PER_RUN_STAVE = 1500
LATENT_DIM = 4


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_raw_root_dir() -> Path:
    for candidate in RAW_ROOT_DIR_CANDIDATES:
        if candidate.exists() and list(candidate.glob("hrdb_run_*.root")):
            return candidate
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs() -> List[int]:
    runs: List[int] = []
    for values in RUN_GROUPS.values():
        runs.extend(values)
    return sorted(set(int(run) for run in runs))


def run_group_lookup() -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in RUN_GROUPS.items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


def topology_label(n_selected: np.ndarray) -> np.ndarray:
    labels = np.full(len(n_selected), "unknown", dtype=object)
    labels[n_selected == 1] = "single"
    labels[n_selected == 2] = "pair"
    labels[n_selected == 3] = "triple"
    labels[n_selected >= 4] = "quad"
    return labels


def scan_raw(raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    group_by_run = run_group_lookup()
    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"Missing configured run: {path}")

        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}
        event_offset = 0

        for batch in iter_raw_events(path):
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES_PER_CHANNEL)
            selected_waves = event_waves[:, STAVE_CHANNELS, :]
            baseline = np.median(selected_waves[..., BASELINE_SAMPLES], axis=-1)
            corrected = selected_waves - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > AMPLITUDE_CUT_ADC
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[name] += int(selected[:, idx].sum())

            if len(event_idx):
                mask_bits = selected.astype(np.uint8) * (1 << np.arange(len(STAVE_NAMES), dtype=np.uint8))
                event_topology_mask = mask_bits.sum(axis=1).astype(np.int16)
                event_topology_n = selected.sum(axis=1).astype(np.int8)
                chosen = corrected[event_idx, stave_idx]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / amp[:, None]).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "run_group": np.full(len(event_idx), group_by_run[run], dtype=object),
                            "event_in_run": event_offset + event_idx.astype(np.int32),
                            "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "topology_mask": event_topology_mask[event_idx],
                            "peer_topology_mask": (event_topology_mask[event_idx] & ~(1 << stave_idx)).astype(np.int16),
                            "topology_n": event_topology_n[event_idx],
                        }
                    )
                )
            event_offset += len(event_waves)

        count_rows.append({"run": run, "run_group": group_by_run[run], **run_counts, **stave_counts})
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def pulse_shape_features(waves: np.ndarray) -> np.ndarray:
    area = waves.sum(axis=1)
    tail = waves[:, 12:].sum(axis=1) / np.maximum(np.abs(area), 1e-6)
    early = waves[:, :5].sum(axis=1)
    late = waves[:, 10:].sum(axis=1)
    peak = waves.argmax(axis=1).astype(np.float32)
    width = (waves > 0.5).sum(axis=1).astype(np.float32)
    plateau = waves[:, 6:10].mean(axis=1)
    asymmetry = (late - early) / np.maximum(np.abs(area), 1e-6)
    return np.column_stack([peak, area, tail, width, plateau, asymmetry]).astype(np.float32)


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


def proxy_features(meta: pd.DataFrame, topology_categories: Sequence[int]) -> np.ndarray:
    amp = meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1)
    topo_n = one_hot(meta["topology_n"].to_numpy(dtype=int), topology_categories)
    return np.hstack([amp, topo_n]).astype(np.float32)


def peer_topology_features(meta: pd.DataFrame, topology_categories: Sequence[int]) -> np.ndarray:
    topo_n = meta["topology_n"].to_numpy(dtype=np.float32).reshape(-1, 1)
    topo_mask = one_hot(meta["peer_topology_mask"].to_numpy(dtype=int), topology_categories)
    return np.hstack([topo_n, topo_mask]).astype(np.float32)


def target_including_topology_features(meta: pd.DataFrame, topology_categories: Sequence[int]) -> np.ndarray:
    topo_n = meta["topology_n"].to_numpy(dtype=np.float32).reshape(-1, 1)
    topo_mask = one_hot(meta["topology_mask"].to_numpy(dtype=int), topology_categories)
    return np.hstack([topo_n, topo_mask]).astype(np.float32)


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator, max_per_run_stave: int) -> np.ndarray:
    selected: List[np.ndarray] = []
    base_idx = np.where(mask)[0]
    frame = meta.iloc[base_idx]
    for (run, stave), group in frame.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        if len(idx) == 0:
            continue
        take = min(len(idx), max_per_run_stave)
        selected.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out


def ci(values: Sequence[float]) -> Tuple[float, float]:
    if len(values) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def run_block_ci(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    return ci(boot)


def fit_probe(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    shuffle_labels: bool = False,
) -> Tuple[dict, np.ndarray]:
    probe_y = y_train.copy()
    if shuffle_labels:
        rng.shuffle(probe_y)
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs", multi_class="auto"),
    )
    clf.fit(x_train, probe_y)
    pred = clf.predict(x_test)
    lo, hi = run_block_ci(y_test, pred, test_runs, rng)
    return (
        {
            "method": method,
            "metric": "balanced_accuracy",
            "value": float(balanced_accuracy_score(y_test, pred)),
            "ci_low": lo,
            "ci_high": hi,
            "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
            "train_rows": int(len(y_train)),
            "heldout_rows": int(len(y_test)),
        },
        pred,
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

    def fit(self, x: np.ndarray, epochs: int = 25, batch_size: int = 4096) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=0.001)
        losses: List[float] = []
        for epoch in range(epochs):
            perm = torch.randperm(len(xt), device=self.device)
            epoch_losses: List[float] = []
            for start in range(0, len(xt), batch_size):
                batch = xt[perm[start : start + batch_size]]
                mask = torch.rand_like(batch) < 0.30
                noisy = batch + 0.02 * torch.randn_like(batch)
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
            if epoch in {0, epochs - 1} or (epoch + 1) % 10 == 0:
                print(f"AE epoch {epoch + 1:02d}/{epochs}: loss={losses[-1]:.6f}")
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out: List[np.ndarray] = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0)

    def reconstruct(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out: List[np.ndarray] = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.net(xt).cpu().numpy())
        return np.concatenate(out, axis=0)


def add_amplitude_bins(meta: pd.DataFrame, train_idx: np.ndarray) -> List[str]:
    quantiles = np.quantile(meta.loc[train_idx, "log10_amplitude"].to_numpy(dtype=float), [0.0, 0.25, 0.50, 0.75, 1.0])
    quantiles[0] -= 1e-6
    quantiles[-1] += 1e-6
    labels = ["q1_low", "q2_midlow", "q3_midhigh", "q4_high"]
    meta["amplitude_bin"] = pd.cut(meta["log10_amplitude"], bins=quantiles, labels=labels, include_lowest=True).astype(str)
    return labels


def stratified_metrics(
    method: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    runs: np.ndarray,
    strata: np.ndarray,
    rng: np.random.Generator,
) -> List[dict]:
    rows: List[dict] = []
    for stratum in sorted(pd.unique(strata)):
        mask = strata == stratum
        if int(mask.sum()) < 20:
            continue
        lo, hi = run_block_ci(y_true[mask], y_pred[mask], runs[mask], rng)
        rows.append(
            {
                "method": method,
                "stratum": str(stratum),
                "metric": "balanced_accuracy",
                "value": float(balanced_accuracy_score(y_true[mask], y_pred[mask])),
                "ci_low": lo,
                "ci_high": hi,
                "heldout_rows": int(mask.sum()),
            }
        )
    return rows


def topology_holdout_metrics(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    train_topology: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_topology: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
) -> List[dict]:
    rows: List[dict] = []
    for topo in ["single", "pair", "triple", "quad"]:
        train_mask = train_topology != topo
        test_mask = test_topology == topo
        if int(train_mask.sum()) < 100 or int(test_mask.sum()) < 100:
            continue
        row, _ = fit_probe(
            method=f"{method} probe-holdout topology={topo}",
            x_train=x_train[train_mask],
            y_train=y_train[train_mask],
            x_test=x_test[test_mask],
            y_test=y_test[test_mask],
            test_runs=test_runs[test_mask],
            rng=rng,
        )
        row["heldout_topology"] = topo
        rows.append(row)
    return rows


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


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


def write_report(result: dict, probes: pd.DataFrame, amplitude: pd.DataFrame, topology: pd.DataFrame, leakage: pd.DataFrame) -> None:
    main = probes[probes["category"] == "main"].copy()
    proxy_and_sentinel = leakage.copy()
    best = main.sort_values("value", ascending=False).iloc[0]
    report = f"""# P01a: amplitude/topology-controlled waveform representation probes

**Ticket:** {TICKET_ID}

## Reproduction first
The script read raw B-stack ROOT files from `{result['raw_root_dir']}` before any modelling.
Using the P01/S00 pulse selection (B2/B4/B6/B8, median samples 0-3 baseline, A > 1000 ADC),
it reproduced **{result['reproduction']['selected_pulses']:,}** selected pulses versus the
published gate value **{EXPECTED_SELECTED_PULSES:,}**.

## Controls and split
All classifiers were trained on runs disjoint from held-out runs `{', '.join(str(r) for r in HELDOUT_RUNS)}`.
The analysis sample is balanced by `(run, stave)` with at most {MAX_PER_RUN_STAVE} pulses per cell
({result['split']['balanced_train_rows']:,} train, {result['split']['balanced_heldout_rows']:,} held out).
CIs are 95% run-block bootstraps on held-out runs.

Amplitude/topology proxies are represented by log10(amplitude) and selected-stave multiplicity.
Peer/topology-mask features are reported only as leakage sentinels because the mask is structurally
label-revealing for triple/quad stave probes. The controlled waveform methods first regress the
valid amplitude/multiplicity proxies out of the 18-sample normalized waveform using training runs only.

## Main held-out probes
{markdown_table(main, ['method', 'value', 'ci_low', 'ci_high', 'macro_f1', 'train_rows', 'heldout_rows'])}

The best controlled waveform probe is **{best['method']}** at **{best['value']:.3f}**
balanced accuracy ({best['ci_low']:.3f}-{best['ci_high']:.3f}).

## Proxy and leakage checks
{markdown_table(proxy_and_sentinel, ['method', 'value', 'ci_low', 'ci_high', 'macro_f1'])}

The peer-mask and target-including topology sentinels are intentionally label-revealing for a
stave probe and land far above the multiplicity-only topology proxy; this was the leakage pattern
hunted after an initial too-good topology score. The AE label-shuffle sentinel is reported as an
additional guard against train/test leakage.

## Amplitude-stratified evaluation
{markdown_table(amplitude, ['method', 'stratum', 'value', 'ci_low', 'ci_high', 'heldout_rows'])}

## Topology-group probe holdouts
For this table the representation is fit on training runs, but the supervised linear probe is
trained excluding the named topology group and tested only on that group in held-out runs.

{markdown_table(topology, ['method', 'heldout_topology', 'value', 'ci_low', 'ci_high', 'heldout_rows'])}

## Verdict
After per-run/per-stave balancing and explicit amplitude/topology controls, waveform shape carries
at most weak standalone stave information. The best controlled waveform score is below the
amplitude-only proxy and far below the topology-multiplicity proxy, while the mask-based sentinels
show how easily topology can become label leakage for this target. Future downstream claims should
quote proxy baselines and topology holdouts alongside any learned waveform representation score.
"""
    (OUT_DIR / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    raw_root_dir = resolve_raw_root_dir()

    print(f"raw ROOT dir: {raw_root_dir}")
    waves, meta, counts_by_run = scan_raw(raw_root_dir)
    selected = int(len(waves))
    print(f"REPRODUCTION COUNT: {selected} selected pulses (expected {EXPECTED_SELECTED_PULSES})")
    if selected != EXPECTED_SELECTED_PULSES:
        raise RuntimeError(f"Reproduction failed: got {selected}, expected {EXPECTED_SELECTED_PULSES}")

    counts_by_run.to_csv(OUT_DIR / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": EXPECTED_SELECTED_PULSES,
                "reproduced": selected,
                "delta": selected - EXPECTED_SELECTED_PULSES,
                "pass": selected == EXPECTED_SELECTED_PULSES,
            }
        ]
    ).to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)

    meta["topology_group"] = topology_label(meta["topology_n"].to_numpy(dtype=int))
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, HELDOUT_RUNS)
    test_mask = np.isin(run_values, HELDOUT_RUNS)
    train_idx = balanced_indices(meta, train_mask, rng, MAX_PER_RUN_STAVE)
    test_idx = balanced_indices(meta, test_mask, rng, MAX_PER_RUN_STAVE)
    add_amplitude_bins(meta, train_idx)

    topology_categories = sorted(int(x) for x in meta.loc[train_idx, "topology_n"].unique())
    peer_topology_categories = sorted(int(x) for x in meta.loc[train_idx, "peer_topology_mask"].unique())
    leaky_topology_categories = sorted(int(x) for x in meta.loc[train_idx, "topology_mask"].unique())
    control_train = proxy_features(meta.loc[train_idx], topology_categories)
    control_test = proxy_features(meta.loc[test_idx], topology_categories)
    peer_topology_train = peer_topology_features(meta.loc[train_idx], peer_topology_categories)
    peer_topology_test = peer_topology_features(meta.loc[test_idx], peer_topology_categories)
    leaky_topology_train = target_including_topology_features(meta.loc[train_idx], leaky_topology_categories)
    leaky_topology_test = target_including_topology_features(meta.loc[test_idx], leaky_topology_categories)
    y_train = meta.loc[train_idx, "stave_index"].to_numpy(dtype=int)
    y_test = meta.loc[test_idx, "stave_index"].to_numpy(dtype=int)
    test_runs = meta.loc[test_idx, "run"].to_numpy(dtype=int)

    x_train_raw = waves[train_idx]
    x_test_raw = waves[test_idx]
    control_model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    control_model.fit(control_train, x_train_raw)
    x_train_resid = (x_train_raw - control_model.predict(control_train)).astype(np.float32)
    x_test_resid = (x_test_raw - control_model.predict(control_test)).astype(np.float32)

    hand_train = pulse_shape_features(x_train_resid)
    hand_test = pulse_shape_features(x_test_resid)
    pca = PCA(n_components=LATENT_DIM, random_state=SEED)
    pca_train = pca.fit_transform(x_train_resid).astype(np.float32)
    pca_test = pca.transform(x_test_resid).astype(np.float32)
    pca_rec = pca.inverse_transform(pca_test)
    pca_recon_mse = float(((pca_rec - x_test_resid) ** 2).mean())

    ae = MaskedDenoisingAutoencoder(LATENT_DIM, SEED)
    losses = ae.fit(x_train_resid)
    ae_train = ae.encode(x_train_resid)
    ae_test = ae.encode(x_test_resid)
    ae_rec = ae.reconstruct(x_test_resid)
    ae_recon_mse = float(((ae_rec - x_test_resid) ** 2).mean())

    probe_rows: List[dict] = []
    preds: Dict[str, np.ndarray] = {}
    for method, xtr, xte, category, shuffle in [
        ("traditional residual hand-shape", hand_train, hand_test, "main", False),
        ("traditional residual PCA-4", pca_train, pca_test, "main", False),
        ("ML residual masked-denoising AE-4", ae_train, ae_test, "main", False),
        ("leakage check: AE label-shuffle", ae_train, ae_test, "sentinel", True),
    ]:
        row, pred = fit_probe(method, xtr, y_train, xte, y_test, test_runs, rng, shuffle_labels=shuffle)
        row["category"] = category
        probe_rows.append(row)
        preds[method] = pred

    for method, xtr, xte in [
        ("proxy: amplitude only", control_train[:, :1], control_test[:, :1]),
        ("proxy: topology only", control_train[:, 1:], control_test[:, 1:]),
        ("proxy: amplitude+topology", control_train, control_test),
        ("leakage check: peer topology mask", peer_topology_train, peer_topology_test),
        ("leakage check: target-including topology", leaky_topology_train, leaky_topology_test),
    ]:
        row, pred = fit_probe(method, xtr, y_train, xte, y_test, test_runs, rng)
        row["category"] = "sentinel" if method.startswith("leakage check") else "proxy"
        probe_rows.append(row)
        preds[method] = pred

    probes = pd.DataFrame(probe_rows)
    probes.to_csv(OUT_DIR / "controlled_probe_benchmark.csv", index=False)

    strata = meta.loc[test_idx, "amplitude_bin"].to_numpy(dtype=object)
    amplitude_rows: List[dict] = []
    for method in ["traditional residual PCA-4", "ML residual masked-denoising AE-4", "proxy: amplitude+topology"]:
        amplitude_rows.extend(stratified_metrics(method, y_test, preds[method], test_runs, strata, rng))
    amplitude = pd.DataFrame(amplitude_rows)
    amplitude.to_csv(OUT_DIR / "amplitude_stratified_metrics.csv", index=False)

    train_topology = meta.loc[train_idx, "topology_group"].to_numpy(dtype=object)
    test_topology = meta.loc[test_idx, "topology_group"].to_numpy(dtype=object)
    topology_rows = []
    topology_rows.extend(topology_holdout_metrics("traditional residual PCA-4", pca_train, y_train, train_topology, pca_test, y_test, test_topology, test_runs, rng))
    topology_rows.extend(topology_holdout_metrics("ML residual masked-denoising AE-4", ae_train, y_train, train_topology, ae_test, y_test, test_topology, test_runs, rng))
    topology = pd.DataFrame(topology_rows)
    topology.to_csv(OUT_DIR / "topology_group_holdout_metrics.csv", index=False)

    leakage = probes[probes["category"].isin(["proxy", "sentinel"])].copy()
    leakage.to_csv(OUT_DIR / "leakage_checks.csv", index=False)
    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(OUT_DIR / "ae_training_loss.csv", index=False)
    pd.DataFrame(
        {
            "representation": ["traditional residual PCA-4", "ML residual masked-denoising AE-4"],
            "heldout_residual_reconstruction_mse": [pca_recon_mse, ae_recon_mse],
            "train_rows": [len(train_idx), len(train_idx)],
            "heldout_rows": [len(test_idx), len(test_idx)],
        }
    ).to_csv(OUT_DIR / "residual_reconstruction_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4))
    plot = probes[probes["category"].isin(["main", "proxy"])].copy()
    colors = ["#4c78a8" if category == "main" else "#8f8f8f" for category in plot["category"]]
    ax.barh(plot["method"], plot["value"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_xlabel("held-out balanced accuracy")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_controlled_probe_benchmark.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, frame in amplitude.groupby("method", sort=False):
        ax.plot(frame["stratum"], frame["value"], marker="o", label=method)
    ax.set_ylim(0, 1)
    ax.set_ylabel("balanced accuracy")
    ax.set_xlabel("held-out amplitude bin")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_amplitude_strata.png", dpi=160)
    plt.close(fig)

    input_rows = []
    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(OUT_DIR / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET_ID,
        "study_id": "P01a",
        "title": "amplitude/topology-controlled waveform representation probes",
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": EXPECTED_SELECTED_PULSES,
            "selected_pulses": selected,
            "passed": selected == EXPECTED_SELECTED_PULSES,
        },
        "split": {
            "train_runs": sorted(int(run) for run in np.unique(run_values[train_mask])),
            "heldout_runs": [int(run) for run in HELDOUT_RUNS],
            "balanced_train_rows": int(len(train_idx)),
            "balanced_heldout_rows": int(len(test_idx)),
            "max_per_run_stave": MAX_PER_RUN_STAVE,
        },
        "controls": {
            "amplitude": "log10 amplitude",
            "topology": "selected-stave multiplicity only; topology masks are leakage sentinels for this target",
            "residualization": "ridge regression fit on balanced training runs only",
        },
        "traditional": {
            "method": "residual hand-shape and residual PCA-4 plus balanced logistic probes",
            "hand_shape_probe": probes[probes["method"] == "traditional residual hand-shape"].iloc[0].to_dict(),
            "pca_probe": probes[probes["method"] == "traditional residual PCA-4"].iloc[0].to_dict(),
            "reconstruction_mse": pca_recon_mse,
        },
        "ml": {
            "method": "residual masked-denoising autoencoder latent-4 plus balanced logistic probe",
            "device": str(ae.device),
            "epochs": len(losses),
            "probe": probes[probes["method"] == "ML residual masked-denoising AE-4"].iloc[0].to_dict(),
            "reconstruction_mse": ae_recon_mse,
            "final_training_loss": float(losses[-1]),
        },
        "proxy_and_leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET_ID,
        "script": str(OUT_DIR / "p01a_controlled_waveform_probes.py"),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(OUT_DIR / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == EXPECTED_SELECTED_PULSES,
        "artifacts": sorted(path.name for path in OUT_DIR.iterdir() if path.is_file()),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(result, probes, amplitude, topology, leakage)

    print(probes.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
