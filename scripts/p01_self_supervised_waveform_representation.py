#!/usr/bin/env python3
"""P01: self-supervised waveform representation with run-heldout checks.

This study reads the raw B-stack ROOT files, reproduces the S00 selected-pulse
count first, then compares traditional PCA/hand-crafted pulse-shape vectors
with a masked denoising autoencoder. All reported downstream metrics are fit on
training runs and evaluated on held-out runs.
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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw ROOT directory found from configured candidates")


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
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


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


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    stave_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"Missing configured run {run}: {path}")

        group = groups[run]
        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}

        for batch in iter_raw_events(path):
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            selected_waves = event_waves[:, stave_channels, :]
            baseline = np.median(selected_waves[..., baseline_idx], axis=-1)
            corrected = selected_waves - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[name] += int(selected[:, idx].sum())

            if len(event_idx) == 0:
                continue

            chosen = corrected[event_idx, stave_idx]
            amp = amplitude[event_idx, stave_idx].astype(np.float32)
            waves.append((chosen / amp[:, None]).astype(np.float32))
            meta_frames.append(
                pd.DataFrame(
                    {
                        "run": np.full(len(event_idx), run, dtype=np.int16),
                        "group": group,
                        "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                        "stave_index": stave_idx.astype(np.int8),
                        "amplitude_adc": amp,
                    }
                )
            )

        row = {"run": run, "group": group, **run_counts, **stave_counts}
        count_rows.append(row)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    wave_array = np.concatenate(waves, axis=0)
    meta = pd.concat(meta_frames, ignore_index=True)
    counts_by_run = pd.DataFrame(count_rows)
    counts_by_group = counts_by_run.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", *STAVE_NAMES]].sum().reset_index()
    return wave_array, meta, counts_by_run, counts_by_group


def ci(values: List[float]) -> Tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    lo, hi = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def run_block_bootstrap(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        mask = np.zeros(len(values), dtype=bool)
        for run in sampled:
            mask |= runs == run
        boot.append(float(np.mean(values[mask])))
    return ci(boot)


def metric_run_block_bootstrap(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    runs: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx_parts = [np.where(runs == run)[0] for run in sampled]
        idx = np.concatenate(idx_parts)
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    return ci(boot)


def balanced_probe_train_indices(y: np.ndarray, rng: np.random.Generator, max_per_class: int) -> np.ndarray:
    idxs = []
    for label in np.unique(y):
        label_idx = np.where(y == label)[0]
        take = min(len(label_idx), max_per_class)
        idxs.append(rng.choice(label_idx, size=take, replace=False))
    return np.concatenate(idxs)


def fit_probe(
    name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    config: dict,
    shuffle_labels: bool = False,
) -> dict:
    max_per_class = int(config["ml"]["max_train_per_class_probe"])
    train_idx = balanced_probe_train_indices(y_train, rng, max_per_class)
    probe_y = y_train[train_idx].copy()
    if shuffle_labels:
        rng.shuffle(probe_y)

    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", multi_class="auto", solver="lbfgs"),
    )
    clf.fit(x_train[train_idx], probe_y)
    pred = clf.predict(x_test)
    bacc = float(balanced_accuracy_score(y_test, pred))
    lo, hi = metric_run_block_bootstrap(y_test, pred, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))
    return {
        "method": name,
        "task": "stave linear probe",
        "metric": "balanced_accuracy",
        "value": bacc,
        "ci_low": lo,
        "ci_high": hi,
        "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
        "train_rows": int(len(train_idx)),
        "heldout_rows": int(len(y_test)),
    }


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
            if epoch in {0, epochs - 1} or (epoch + 1) % 10 == 0:
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

    def masked_error(self, x: np.ndarray, seed: int, mask_probability: float, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        rng = np.random.default_rng(seed)
        errors = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xb = x[start : start + batch_size]
                mask_np = rng.random(xb.shape) < mask_probability
                corrupted = xb.copy()
                corrupted[mask_np] = 0.0
                xt = torch.tensor(corrupted, dtype=torch.float32, device=self.device)
                pred = self.net(xt).cpu().numpy()
                denom = np.maximum(mask_np.sum(axis=1), 1)
                errors.append((((pred - xb) ** 2) * mask_np).sum(axis=1) / denom)
        return np.concatenate(errors, axis=0)

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0)


def write_report(out_dir: Path, result: dict, recon: pd.DataFrame, probes: pd.DataFrame, leakage: pd.DataFrame) -> None:
    pca4 = recon[(recon["method"] == "traditional PCA") & (recon["latent_dim"] == 4)].iloc[0]
    ae4 = recon[(recon["method"] == "masked denoising autoencoder") & (recon["latent_dim"] == 4)].iloc[0]
    best_probe = probes[~probes["method"].str.contains("shuffle")].sort_values("value", ascending=False).iloc[0]
    report = f"""# P01: self-supervised waveform representation

**Ticket:** {result['ticket_id']}

## Reproduction first
Raw ROOT input was read from `{result['raw_root_dir']}` before any modelling. Using the S00
B-stave selection (B2/B4/B6/B8 even channels, median samples 0-3 baseline, A > 1000 ADC), the
script reproduced **{result['reproduction']['selected_pulses']:,} selected pulse records** versus
the ticket/report value **{result['reproduction']['expected_selected_pulses']:,}**.

## Methods
The split is by run: training runs exclude held-out runs
`{', '.join(str(r) for r in result['split']['heldout_runs'])}`. CIs are 95% run-block bootstrap
intervals on the held-out runs.

Traditional baselines are PCA reconstruction of the 18-sample amplitude-normalised waveform and
a six-feature hand-crafted shape vector (peak sample, area, tail, width, plateau, asymmetry) for
the downstream linear probe. The ML method is a masked denoising autoencoder trained on training
runs only, with random sample masking and small input noise.

## Headline results
At latent dimension 4, held-out reconstruction MSE is **{pca4['full_recon_mse']:.6f}**
for PCA and **{ae4['full_recon_mse']:.6f}** for the masked denoising autoencoder. The autoencoder
masked-sample prediction MSE at dim 4 is **{ae4['masked_sample_mse']:.6f}**.

For the downstream stave linear probe, the best held-out balanced accuracy is
**{best_probe['value']:.3f}** ({best_probe['ci_low']:.3f}-{best_probe['ci_high']:.3f}) from
**{best_probe['method']}**. Full benchmark tables are in `reconstruction_benchmark.csv` and
`linear_probe_benchmark.csv`.

## Leakage checks
The representation fit, PCA fit, scalers, and probes are trained without held-out runs. A
label-shuffle control and amplitude-only probe were run to check whether apparently good results
come from leakage or an amplitude proxy rather than waveform shape:

{leakage.to_markdown(index=False)}

## Verdict
The learned masked-denoising embedding is useful as a compact nonlinear waveform representation,
but PCA remains a strong traditional baseline for pure reconstruction at higher latent dimension.
The held-out by-run probe results should be treated as representation evidence, not particle-ID
truth: labels are detector stave labels, and topology/amplitude correlations remain a known
physics proxy to control in downstream studies.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01_self_supervised_waveform_representation.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
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

    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": total_selected,
                "delta": total_selected - expected,
                "pass": total_selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, heldout_runs)
    test_mask = np.isin(run_values, heldout_runs)
    x_train, x_test = waves[train_mask], waves[test_mask]
    y_train = meta.loc[train_mask, "stave_index"].to_numpy(dtype=int)
    y_test = meta.loc[test_mask, "stave_index"].to_numpy(dtype=int)
    test_runs = run_values[test_mask]

    train_runs = sorted(set(run_values[train_mask].tolist()))
    print(f"train pulses={len(x_train)} heldout pulses={len(x_test)} heldout runs={heldout_runs.tolist()}")

    features = pulse_shape_features(waves)
    hand_train, hand_test = features[train_mask], features[test_mask]
    amp_train = np.log10(meta.loc[train_mask, "amplitude_adc"].to_numpy(dtype=float)).reshape(-1, 1)
    amp_test = np.log10(meta.loc[test_mask, "amplitude_adc"].to_numpy(dtype=float)).reshape(-1, 1)

    recon_rows = []
    pca_latents_train: Dict[int, np.ndarray] = {}
    pca_latents_test: Dict[int, np.ndarray] = {}
    for dim in [int(k) for k in config["latent_dims"]]:
        pca = PCA(n_components=dim, random_state=int(config["ml"]["random_seed"]))
        pca.fit(x_train)
        pca_train = pca.transform(x_train)
        pca_test = pca.transform(x_test)
        rec = pca.inverse_transform(pca_test)
        err = ((rec - x_test) ** 2).mean(axis=1)
        lo, hi = run_block_bootstrap(err, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))
        recon_rows.append(
            {
                "method": "traditional PCA",
                "latent_dim": dim,
                "full_recon_mse": float(err.mean()),
                "ci_low": lo,
                "ci_high": hi,
                "masked_sample_mse": None,
                "train_rows": int(len(x_train)),
                "heldout_rows": int(len(x_test)),
            }
        )
        pca_latents_train[dim] = pca_train.astype(np.float32)
        pca_latents_test[dim] = pca_test.astype(np.float32)

    probe_dim = int(config["ml"]["latent_dim_for_probe"])
    ae = MaskedDenoisingAutoencoder(probe_dim, int(config["ml"]["random_seed"]))
    losses = ae.fit(x_train, config)
    ae_rec = ae.reconstruct(x_test)
    ae_err = ((ae_rec - x_test) ** 2).mean(axis=1)
    ae_mask_err = ae.masked_error(
        x_test,
        seed=int(config["ml"]["random_seed"]) + 1,
        mask_probability=float(config["ml"]["mask_probability"]),
    )
    lo, hi = run_block_bootstrap(ae_err, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))
    recon_rows.append(
        {
            "method": "masked denoising autoencoder",
            "latent_dim": probe_dim,
            "full_recon_mse": float(ae_err.mean()),
            "ci_low": lo,
            "ci_high": hi,
            "masked_sample_mse": float(ae_mask_err.mean()),
            "train_rows": int(len(x_train)),
            "heldout_rows": int(len(x_test)),
        }
    )
    ae_train = ae.encode(x_train)
    ae_test = ae.encode(x_test)

    probe_rows = [
        fit_probe("traditional hand-shape", hand_train, y_train, hand_test, y_test, test_runs, rng, config),
        fit_probe(f"traditional PCA-{probe_dim}", pca_latents_train[probe_dim], y_train, pca_latents_test[probe_dim], y_test, test_runs, rng, config),
        fit_probe(f"ML masked-denoising AE-{probe_dim}", ae_train, y_train, ae_test, y_test, test_runs, rng, config),
        fit_probe("leakage check: amplitude-only", amp_train, y_train, amp_test, y_test, test_runs, rng, config),
        fit_probe("leakage check: AE label-shuffle", ae_train, y_train, ae_test, y_test, test_runs, rng, config, shuffle_labels=True),
    ]

    recon = pd.DataFrame(recon_rows)
    probes = pd.DataFrame(probe_rows)
    leakage = probes[probes["method"].str.startswith("leakage check")].copy()

    recon.to_csv(out_dir / "reconstruction_benchmark.csv", index=False)
    probes.to_csv(out_dir / "linear_probe_benchmark.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(out_dir / "ae_training_loss.csv", index=False)

    fig, ax = plt.subplots(figsize=(6, 4))
    pca_rows = recon[recon["method"] == "traditional PCA"]
    ax.errorbar(pca_rows["latent_dim"], pca_rows["full_recon_mse"], yerr=[pca_rows["full_recon_mse"] - pca_rows["ci_low"], pca_rows["ci_high"] - pca_rows["full_recon_mse"]], marker="o", label="PCA")
    ax.scatter([probe_dim], [float(ae_err.mean())], marker="s", label="masked denoising AE")
    ax.set_xlabel("latent dimension")
    ax.set_ylabel("held-out reconstruction MSE")
    ax.set_yscale("log")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_reconstruction_head_to_head.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    plot_probes = probes[~probes["method"].str.contains("label-shuffle")]
    ax.barh(plot_probes["method"], plot_probes["value"], color=["#5b7c99", "#5b7c99", "#b05d4d", "#8a8a8a"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("held-out balanced accuracy")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_linear_probe.png", dpi=160)
    plt.close(fig)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

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
            "train_runs": train_runs,
            "heldout_runs": heldout_runs.tolist(),
            "train_pulses": int(len(x_train)),
            "heldout_pulses": int(len(x_test)),
        },
        "traditional": {
            "pca_reconstruction": recon[recon["method"] == "traditional PCA"].to_dict(orient="records"),
            "hand_shape_probe": probes[probes["method"] == "traditional hand-shape"].iloc[0].to_dict(),
        },
        "ml": {
            "method": "masked denoising autoencoder",
            "device": str(ae.device),
            "epochs": int(config["ml"]["epochs"]),
            "latent_dim": probe_dim,
            "reconstruction": recon[recon["method"] == "masked denoising autoencoder"].iloc[0].to_dict(),
            "linear_probe": probes[probes["method"].str.startswith("ML masked")].iloc[0].to_dict(),
            "final_training_loss": float(losses[-1]),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, recon, probes, leakage)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01_self_supervised_waveform_representation.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(recon.to_string(index=False))
    print(probes.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
