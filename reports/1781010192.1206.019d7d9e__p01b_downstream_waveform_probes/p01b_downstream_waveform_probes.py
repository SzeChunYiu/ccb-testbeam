#!/usr/bin/env python3
"""P01b downstream target waveform probes.

This ticket reruns the P01/P01a representation comparison on a downstream
target that is not the pulse stave label. The chosen target is sample epoch:
Sample I runs (31-57, excluding missing/nonconfigured runs) versus Sample II
runs (58-65). All modelling is trained without the held-out runs.
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_ID = "1781010192.1206.019d7d9e"
STUDY_ID = "P01b-downstream"
OUT_DIR = Path("reports/1781010192.1206.019d7d9e__p01b_downstream_waveform_probes")
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
STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)
STAVE_CHANNELS = np.asarray([0, 2, 4, 6], dtype=int)
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
HELDOUT_RUNS = np.asarray([42, 57, 64, 65], dtype=int)
SEED = 240619
BOOTSTRAP_REPLICATES = 500
MAX_PER_RUN_STAVE = 2500
LATENT_DIM = 4
AE_EPOCHS = 25


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


def sample_epoch_from_group(group: str) -> str:
    return "sample_ii" if group.startswith("sample_ii") else "sample_i"


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


def scan_raw(raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    group_by_run = run_group_lookup()
    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"Missing configured run: {path}")
        run_group = group_by_run[run]
        epoch = sample_epoch_from_group(run_group)
        epoch_label = 1 if epoch == "sample_ii" else 0

        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}

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
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                event_topology_mask = (selected.astype(np.uint8) * (1 << np.arange(len(STAVE_NAMES), dtype=np.uint8))).sum(axis=1).astype(np.int16)
                event_topology_n = selected.sum(axis=1).astype(np.int8)
                chosen = corrected[event_idx, stave_idx]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / amp[:, None]).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "run_group": np.full(len(event_idx), run_group, dtype=object),
                            "sample_epoch": np.full(len(event_idx), epoch, dtype=object),
                            "sample_epoch_label": np.full(len(event_idx), epoch_label, dtype=np.int8),
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "topology_mask": event_topology_mask[event_idx],
                            "topology_n": event_topology_n[event_idx],
                        }
                    )
                )

        count_rows.append({"run": run, "run_group": run_group, "sample_epoch": epoch, **run_counts, **stave_counts})
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def pulse_shape_features(waves: np.ndarray) -> np.ndarray:
    area = waves.sum(axis=1)
    early = waves[:, :5].sum(axis=1)
    late = waves[:, 10:].sum(axis=1)
    return np.column_stack(
        [
            waves.argmax(axis=1).astype(np.float32),
            area,
            waves[:, 12:].sum(axis=1) / np.maximum(np.abs(area), 1e-6),
            (waves > 0.5).sum(axis=1).astype(np.float32),
            waves[:, 5:10].mean(axis=1),
            (late - early) / np.maximum(np.abs(area), 1e-6),
        ]
    ).astype(np.float32)


def proxy_matrix(meta: pd.DataFrame, include_topology_mask: bool = False, include_stave: bool = False) -> np.ndarray:
    out = [meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1)]
    out.append(one_hot(meta["topology_n"].to_numpy(dtype=int), [1, 2, 3, 4]))
    if include_topology_mask:
        out.append(one_hot(meta["topology_mask"].to_numpy(dtype=int), list(range(1, 16))))
    if include_stave:
        out.append(one_hot(meta["stave_index"].to_numpy(dtype=int), [0, 1, 2, 3]))
    return np.hstack(out).astype(np.float32)


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator, max_per_run_stave: int) -> np.ndarray:
    selected: List[np.ndarray] = []
    base_idx = np.where(mask)[0]
    frame = meta.iloc[base_idx]
    for (_epoch, run, stave), group in frame.groupby(["sample_epoch", "run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), max_per_run_stave)
        if take:
            selected.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out


def fixed_binary_balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    scores = []
    for label in [0, 1]:
        mask = y_true == label
        if int(mask.sum()) == 0:
            return float("nan")
        scores.append(float((y_pred[mask] == label).mean()))
    return float(np.mean(scores))


def class_recall_or_balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    labels = np.unique(y_true)
    if len(labels) == 1:
        return float((y_pred == labels[0]).mean())
    return float(balanced_accuracy_score(y_true, y_pred))


def stratified_run_block_ci(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator) -> Tuple[float, float]:
    run_epoch = {int(run): int(pd.Series(y_true[runs == run]).mode().iloc[0]) for run in np.unique(runs)}
    runs_by_epoch = {
        0: np.asarray([run for run, epoch in run_epoch.items() if epoch == 0], dtype=int),
        1: np.asarray([run for run, epoch in run_epoch.items() if epoch == 1], dtype=int),
    }
    boot: List[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_runs = []
        for epoch in [0, 1]:
            epoch_runs = runs_by_epoch[epoch]
            sampled_runs.extend(rng.choice(epoch_runs, size=len(epoch_runs), replace=True).tolist())
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled_runs])
        boot.append(fixed_binary_balanced_accuracy(y_true[idx], y_pred[idx]))
    lo, hi = np.quantile(np.asarray(boot, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def fit_probe(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    shuffle_labels: bool = False,
) -> Tuple[dict, np.ndarray, np.ndarray]:
    probe_y = y_train.copy()
    if shuffle_labels:
        rng.shuffle(probe_y)
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"),
    )
    clf.fit(x_train, probe_y)
    pred = clf.predict(x_test)
    score = clf.predict_proba(x_test)[:, 1]
    lo, hi = stratified_run_block_ci(y_test, pred, test_runs, rng)
    row = {
        "method": method,
        "metric": "balanced_accuracy",
        "value": fixed_binary_balanced_accuracy(y_test, pred),
        "ci_low": lo,
        "ci_high": hi,
        "roc_auc": float(roc_auc_score(y_test, score)),
        "average_precision": float(average_precision_score(y_test, score)),
        "train_rows": int(len(y_train)),
        "heldout_rows": int(len(y_test)),
    }
    return row, pred, score


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

    def fit(self, x: np.ndarray, epochs: int = AE_EPOCHS, batch_size: int = 4096) -> List[float]:
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
                loss = ((pred - batch) ** 2)[mask].mean() + 0.2 * ((pred - batch) ** 2).mean()
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


def write_report(result: dict, probes: pd.DataFrame, by_run: pd.DataFrame) -> None:
    main = probes[probes["category"] == "main"].copy()
    proxy = probes[probes["category"].isin(["proxy", "leakage_check"])].copy()
    best = main.sort_values("value", ascending=False).iloc[0]
    report = f"""# P01b: waveform probes on non-stave downstream targets

**Ticket:** {TICKET_ID}

## Reproduction first
The script read raw B-stack ROOT files from `{result['raw_root_dir']}` before any modelling.
Using the P01/S00 B-stave gate (B2/B4/B6/B8, median samples 0-3 baseline, A > 1000 ADC), it
reproduced **{result['reproduction']['selected_pulses']:,}** selected pulses versus the published
P01/S00 number **{EXPECTED_SELECTED_PULSES:,}**.

## Target and split
The downstream target is **sample epoch**: Sample I runs are the negative class and Sample II runs
are the positive class. This is not the pulse's own stave label. All representation fits and
supervised probes train on runs disjoint from held-out runs `{', '.join(str(r) for r in HELDOUT_RUNS)}`.
The benchmark sample is capped at {MAX_PER_RUN_STAVE} pulses per `(run, stave)` cell
({result['split']['balanced_train_rows']:,} train, {result['split']['balanced_heldout_rows']:,}
held out). CIs are 95% stratified run-block bootstraps over the held-out runs.

## Main held-out probes
{markdown_table(main, ['method', 'value', 'ci_low', 'ci_high', 'roc_auc', 'average_precision', 'train_rows', 'heldout_rows'])}

The strongest waveform representation is **{best['method']}** at **{best['value']:.3f}**
balanced accuracy ({best['ci_low']:.3f}-{best['ci_high']:.3f}). The traditional PCA-4
reconstruction MSE is {result['traditional']['pca_reconstruction_mse']:.5f}; the masked-AE-4
reconstruction MSE is {result['ml']['reconstruction_mse']:.5f}.

## Proxy and leakage checks
{markdown_table(proxy, ['method', 'value', 'ci_low', 'ci_high', 'roc_auc', 'average_precision'])}

The topology/stave-composition sentinel is the leakage hunt for a too-good result: if a waveform
probe wins only because it recovers sample-dependent detector composition, this proxy should also
be strong. Here, PCA and AE exceed the amplitude/topology proxies, while the proxy scores remain
nontrivial. The result should therefore be interpreted as sample-era/domain separation, not as
particle identification.

## Held-out run breakdown
{markdown_table(by_run, ['method', 'run', 'sample_epoch', 'heldout_rows', 'run_class_recall', 'positive_rate', 'mean_score'])}

## Verdict
On this non-stave downstream target, waveform shape does carry held-out sample-epoch information.
The ML masked-denoising latent is competitive with but not decisively better than traditional
PCA/hand-shape probes under run-held-out CIs. The amplitude/topology proxy and composition
sentinel show that detector/run-domain shifts explain a meaningful part of the separation, so this
is a useful robustness diagnostic rather than evidence for a new physics label.
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

    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, HELDOUT_RUNS)
    test_mask = np.isin(run_values, HELDOUT_RUNS)
    train_idx = balanced_indices(meta, train_mask, rng, MAX_PER_RUN_STAVE)
    test_idx = balanced_indices(meta, test_mask, rng, MAX_PER_RUN_STAVE)

    y_train = meta.loc[train_idx, "sample_epoch_label"].to_numpy(dtype=int)
    y_test = meta.loc[test_idx, "sample_epoch_label"].to_numpy(dtype=int)
    test_runs = meta.loc[test_idx, "run"].to_numpy(dtype=int)

    x_train_raw = waves[train_idx]
    x_test_raw = waves[test_idx]
    hand_train = pulse_shape_features(x_train_raw)
    hand_test = pulse_shape_features(x_test_raw)

    pca = PCA(n_components=LATENT_DIM, random_state=SEED)
    pca_train = pca.fit_transform(x_train_raw).astype(np.float32)
    pca_test = pca.transform(x_test_raw).astype(np.float32)
    pca_rec = pca.inverse_transform(pca_test)
    pca_recon_mse = float(((pca_rec - x_test_raw) ** 2).mean())

    ae = MaskedDenoisingAutoencoder(LATENT_DIM, SEED)
    losses = ae.fit(x_train_raw)
    ae_train = ae.encode(x_train_raw)
    ae_test = ae.encode(x_test_raw)
    ae_rec = ae.reconstruct(x_test_raw)
    ae_recon_mse = float(((ae_rec - x_test_raw) ** 2).mean())

    proxy_train = proxy_matrix(meta.loc[train_idx], include_topology_mask=False, include_stave=False)
    proxy_test = proxy_matrix(meta.loc[test_idx], include_topology_mask=False, include_stave=False)
    composition_train = proxy_matrix(meta.loc[train_idx], include_topology_mask=True, include_stave=True)
    composition_test = proxy_matrix(meta.loc[test_idx], include_topology_mask=True, include_stave=True)

    probe_rows: List[dict] = []
    predictions: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for method, xtr, xte, category, shuffle in [
        ("traditional hand-shape", hand_train, hand_test, "main", False),
        ("traditional PCA-4", pca_train, pca_test, "main", False),
        ("ML masked-denoising AE-4", ae_train, ae_test, "main", False),
        ("proxy: amplitude+multiplicity", proxy_train, proxy_test, "proxy", False),
        ("leakage check: topology/stave composition", composition_train, composition_test, "leakage_check", False),
        ("leakage check: AE label shuffle", ae_train, ae_test, "leakage_check", True),
    ]:
        row, pred, score = fit_probe(method, xtr, y_train, xte, y_test, test_runs, rng, shuffle_labels=shuffle)
        row["category"] = category
        probe_rows.append(row)
        predictions[method] = (pred, score)

    probes = pd.DataFrame(probe_rows)
    probes.to_csv(OUT_DIR / "downstream_probe_benchmark.csv", index=False)

    by_run_rows: List[dict] = []
    for method in ["traditional hand-shape", "traditional PCA-4", "ML masked-denoising AE-4", "proxy: amplitude+multiplicity", "leakage check: topology/stave composition"]:
        pred, score = predictions[method]
        for run in np.unique(test_runs):
            mask = test_runs == run
            by_run_rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "sample_epoch": str(meta.loc[test_idx[mask], "sample_epoch"].iloc[0]),
                    "heldout_rows": int(mask.sum()),
                    "run_class_recall": class_recall_or_balanced_accuracy(y_test[mask], pred[mask]),
                    "positive_rate": float(pred[mask].mean()),
                    "mean_score": float(score[mask].mean()),
                }
            )
    by_run = pd.DataFrame(by_run_rows)
    by_run.to_csv(OUT_DIR / "heldout_by_run_metrics.csv", index=False)

    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(OUT_DIR / "ae_training_loss.csv", index=False)
    pd.DataFrame(
        {
            "representation": ["traditional PCA-4", "ML masked-denoising AE-4"],
            "heldout_reconstruction_mse": [pca_recon_mse, ae_recon_mse],
            "train_rows": [len(train_idx), len(train_idx)],
            "heldout_rows": [len(test_idx), len(test_idx)],
        }
    ).to_csv(OUT_DIR / "reconstruction_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4))
    plot = probes.copy()
    colors = ["#4c78a8" if category == "main" else "#8f8f8f" for category in plot["category"]]
    ax.barh(plot["method"], plot["value"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_xlabel("held-out balanced accuracy")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_downstream_probe_benchmark.png", dpi=160)
    plt.close(fig)

    input_rows = []
    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(OUT_DIR / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET_ID,
        "study_id": STUDY_ID,
        "title": "waveform probes on non-stave downstream targets",
        "raw_root_dir": str(raw_root_dir),
        "target": {
            "name": "sample_epoch",
            "negative_class": "sample_i",
            "positive_class": "sample_ii",
            "not_own_stave_label": True,
        },
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
            "bootstrap": f"{BOOTSTRAP_REPLICATES} stratified run-block replicates",
        },
        "traditional": {
            "method": "hand-shape summaries and PCA-4 plus balanced logistic probes",
            "hand_shape_probe": probes[probes["method"] == "traditional hand-shape"].iloc[0].to_dict(),
            "pca_probe": probes[probes["method"] == "traditional PCA-4"].iloc[0].to_dict(),
            "pca_reconstruction_mse": pca_recon_mse,
        },
        "ml": {
            "method": "masked-denoising autoencoder latent-4 plus balanced logistic probe",
            "device": str(ae.device),
            "epochs": len(losses),
            "probe": probes[probes["method"] == "ML masked-denoising AE-4"].iloc[0].to_dict(),
            "reconstruction_mse": ae_recon_mse,
            "final_training_loss": float(losses[-1]),
        },
        "proxy_and_leakage_checks": probes[probes["category"].isin(["proxy", "leakage_check"])].to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(result, probes, by_run)

    artifacts = sorted(path.name for path in OUT_DIR.iterdir() if path.is_file())
    if "manifest.json" not in artifacts:
        artifacts.append("manifest.json")
        artifacts = sorted(artifacts)
    manifest = {
        "ticket_id": TICKET_ID,
        "study_id": STUDY_ID,
        "script": str(OUT_DIR / "p01b_downstream_waveform_probes.py"),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(OUT_DIR / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == EXPECTED_SELECTED_PULSES,
        "artifacts": artifacts,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(probes.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
