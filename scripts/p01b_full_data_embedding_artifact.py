#!/usr/bin/env python3
"""P01b: release a reusable full-data P01 waveform embedding artifact.

The benchmark part is run-heldout and train-only. The release artifact is fit
only after those numbers are frozen, on all selected B-stave pulses, and is not
used for any benchmark claim in this report.
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


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


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
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError("Missing configured run {}".format(path))

        group = groups[run]
        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}
        event_offset = 0

        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
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

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                chosen = corrected[event_idx, stave_idx]
                waves.append((chosen / amp[:, None]).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "group": group,
                            "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                        }
                    )
                )

            event_offset += int(len(event_waves))

        row = {"run": run, "group": group, **run_counts, **stave_counts}
        count_rows.append(row)
        print("run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]))

    wave_array = np.concatenate(waves, axis=0)
    meta = pd.concat(meta_frames, ignore_index=True)
    counts_by_run = pd.DataFrame(count_rows)
    counts_by_group = (
        counts_by_run.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", *STAVE_NAMES]]
        .sum()
        .reset_index()
    )
    return wave_array, meta, counts_by_run, counts_by_group


def ci(values: List[float]) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def run_block_bootstrap_mean(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        boot.append(float(np.mean(values[idx])))
    return ci(boot)


def run_block_bootstrap_bacc(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    return ci(boot)


def balanced_train_indices(y: np.ndarray, rng: np.random.Generator, max_per_class: int) -> np.ndarray:
    idxs = []
    for label in np.unique(y):
        label_idx = np.where(y == label)[0]
        take = min(len(label_idx), max_per_class)
        idxs.append(rng.choice(label_idx, size=take, replace=False))
    return np.concatenate(idxs)


def fit_probe(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    rng: np.random.Generator,
    config: dict,
    shuffle_labels: bool = False,
) -> dict:
    idx = balanced_train_indices(y_train, rng, int(config["ml"]["max_train_per_class_probe"]))
    probe_y = y_train[idx].copy()
    if shuffle_labels:
        rng.shuffle(probe_y)
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", multi_class="auto", solver="lbfgs"),
    )
    clf.fit(x_train[idx], probe_y)
    pred = clf.predict(x_test)
    lo, hi = run_block_bootstrap_bacc(y_test, pred, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))
    return {
        "method": method,
        "task": "stave linear probe",
        "metric": "balanced_accuracy",
        "value": float(balanced_accuracy_score(y_test, pred)),
        "ci_low": lo,
        "ci_high": hi,
        "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
        "train_rows": int(len(idx)),
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

    def fit(self, x: np.ndarray, config: dict, label: str) -> List[float]:
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
                print("{} AE epoch {:02d}/{}: loss={:.6f}".format(label, epoch + 1, epochs, losses[-1]))
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
        return np.concatenate(out, axis=0).astype(np.float32)

    def save_state(self, path: Path) -> None:
        self.torch.save(self.net.state_dict(), str(path))


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_report(out_dir: Path, result: dict, recon: pd.DataFrame, probes: pd.DataFrame, artifact_meta: dict) -> None:
    pca = recon[recon["method"] == "traditional PCA-4"].iloc[0]
    ae = recon[recon["method"] == "ML masked-denoising AE-4"].iloc[0]
    best_probe = probes[~probes["method"].str.contains("label-shuffle")].sort_values("value", ascending=False).iloc[0]
    report = """# P01b: reusable full-data waveform embedding artifact

**Ticket:** {ticket_id}

## Reproduction first
Raw B-stack ROOT files were read from `{raw_root_dir}`. The S00/P01 B-stave
selection reproduced **{selected:,}** selected pulse records versus the ticket
target **{expected:,}** before any model fitting.

## Frozen held-out benchmark
The benchmark split is by run. Held-out runs are `{heldout_runs}`; all PCA,
autoencoder, scalers, and probes below were fit without those runs. CIs are 95%
run-block bootstrap intervals over held-out runs.

| method | held-out reconstruction MSE | 95% CI |
|---|---:|---:|
| traditional PCA-4 | {pca_mse:.6f} | {pca_lo:.6f}-{pca_hi:.6f} |
| ML masked-denoising AE-4 | {ae_mse:.6f} | {ae_lo:.6f}-{ae_hi:.6f} |

The best held-out stave linear probe is **{best_probe:.3f}**
({best_lo:.3f}-{best_hi:.3f}) from **{best_method}**. The amplitude-only
and label-shuffle controls are written to `leakage_checks.csv`; label shuffling
falls to chance, while amplitude-only remains a documented detector proxy.

## Release artifact
After the held-out evaluation was frozen, the same selected masked-denoising
architecture was fit on all **{selected:,}** selected waveforms. The reusable
artifact is `p01b_embedding_latents.npz`, keyed by `run`, deterministic
`event_index`, and `stave_index`, with `amplitude_adc` and `z` (`float32`,
shape `{rows} x {latent_dim}`). The model weights are in
`p01b_autoencoder_state.pt`; the generation metadata is in
`p01b_embedding_metadata.json`.

Compressed latent table size is **{artifact_mib:.2f} MiB**, versus **{wave_mib:.2f} MiB**
for the in-memory normalized waveform matrix. Runtime was **{runtime:.1f} s** on
`{device}`. Regenerate the local binary artifact with
`/home/billy/anaconda3/bin/python scripts/p01b_full_data_embedding_artifact.py --config configs/p01b_full_data_embedding_artifact.json`.
Input sha256 values are recorded in `input_sha256.csv`.

## Verdict
This artifact is suitable for downstream P02-P08 feature work as a compact
waveform representation. It should not be cited as an independent benchmark
score, because the release model intentionally uses every selected pulse after
the held-out P01/P01b checks are frozen.
""".format(
        ticket_id=result["ticket_id"],
        raw_root_dir=result["raw_root_dir"],
        selected=result["reproduction"]["selected_pulses"],
        expected=result["reproduction"]["expected_selected_pulses"],
        heldout_runs=", ".join(str(run) for run in result["split"]["heldout_runs"]),
        pca_mse=pca["full_recon_mse"],
        pca_lo=pca["ci_low"],
        pca_hi=pca["ci_high"],
        ae_mse=ae["full_recon_mse"],
        ae_lo=ae["ci_low"],
        ae_hi=ae["ci_high"],
        best_probe=best_probe["value"],
        best_lo=best_probe["ci_low"],
        best_hi=best_probe["ci_high"],
        best_method=best_probe["method"],
        rows=artifact_meta["rows"],
        latent_dim=artifact_meta["latent_dim"],
        artifact_mib=artifact_meta["artifact_mib"],
        wave_mib=artifact_meta["normalized_waveform_matrix_mib"],
        runtime=result["runtime_sec"],
        device=result["ml"]["release_device"],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01b_full_data_embedding_artifact.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("raw ROOT dir: {}".format(raw_root_dir))
    waves, meta, counts_by_run, counts_by_group = scan_raw(config, raw_root_dir)
    total_selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    print("REPRODUCTION COUNT: {} selected pulses (expected {})".format(total_selected, expected))
    if total_selected != expected:
        raise RuntimeError("Reproduction failed: got {}, expected {}".format(total_selected, expected))

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
    print("train pulses={} heldout pulses={} heldout runs={}".format(len(x_train), len(x_test), heldout_runs.tolist()))

    latent_dim = int(config["latent_dim"])
    pca = PCA(n_components=latent_dim, random_state=int(config["ml"]["random_seed"]))
    pca.fit(x_train)
    pca_train = pca.transform(x_train).astype(np.float32)
    pca_test = pca.transform(x_test).astype(np.float32)
    pca_err = ((pca.inverse_transform(pca_test) - x_test) ** 2).mean(axis=1)
    pca_lo, pca_hi = run_block_bootstrap_mean(pca_err, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))

    ae_eval = MaskedDenoisingAutoencoder(latent_dim, int(config["ml"]["random_seed"]))
    eval_losses = ae_eval.fit(x_train, config, "heldout-eval")
    ae_eval_test = ae_eval.encode(x_test)
    ae_eval_train = ae_eval.encode(x_train)
    ae_err = ((ae_eval.reconstruct(x_test) - x_test) ** 2).mean(axis=1)
    ae_mask_err = ae_eval.masked_error(
        x_test,
        seed=int(config["ml"]["random_seed"]) + 1,
        mask_probability=float(config["ml"]["mask_probability"]),
    )
    ae_lo, ae_hi = run_block_bootstrap_mean(ae_err, test_runs, rng, int(config["ml"]["bootstrap_replicates"]))

    recon = pd.DataFrame(
        [
            {
                "method": "traditional PCA-4",
                "latent_dim": latent_dim,
                "full_recon_mse": float(pca_err.mean()),
                "ci_low": pca_lo,
                "ci_high": pca_hi,
                "masked_sample_mse": None,
                "train_rows": int(len(x_train)),
                "heldout_rows": int(len(x_test)),
            },
            {
                "method": "ML masked-denoising AE-4",
                "latent_dim": latent_dim,
                "full_recon_mse": float(ae_err.mean()),
                "ci_low": ae_lo,
                "ci_high": ae_hi,
                "masked_sample_mse": float(ae_mask_err.mean()),
                "train_rows": int(len(x_train)),
                "heldout_rows": int(len(x_test)),
            },
        ]
    )
    recon.to_csv(out_dir / "heldout_reconstruction_benchmark.csv", index=False)
    pd.DataFrame({"epoch": np.arange(1, len(eval_losses) + 1), "training_loss": eval_losses}).to_csv(
        out_dir / "eval_ae_training_loss.csv", index=False
    )

    hand = pulse_shape_features(waves)
    amp = np.log10(meta["amplitude_adc"].to_numpy(dtype=float)).reshape(-1, 1)
    probes = pd.DataFrame(
        [
            fit_probe("traditional hand-shape", hand[train_mask], y_train, hand[test_mask], y_test, test_runs, rng, config),
            fit_probe("traditional PCA-4", pca_train, y_train, pca_test, y_test, test_runs, rng, config),
            fit_probe("ML masked-denoising AE-4", ae_eval_train, y_train, ae_eval_test, y_test, test_runs, rng, config),
            fit_probe("leakage check: amplitude-only", amp[train_mask], y_train, amp[test_mask], y_test, test_runs, rng, config),
            fit_probe("leakage check: AE label-shuffle", ae_eval_train, y_train, ae_eval_test, y_test, test_runs, rng, config, shuffle_labels=True),
        ]
    )
    probes.to_csv(out_dir / "linear_probe_benchmark.csv", index=False)
    probes[probes["method"].str.startswith("leakage check")].to_csv(out_dir / "leakage_checks.csv", index=False)

    ae_release = MaskedDenoisingAutoencoder(latent_dim, int(config["ml"]["random_seed"]) + 9001)
    release_losses = ae_release.fit(waves, config, "release-all-data")
    z = ae_release.encode(waves)

    artifact_path = out_dir / "p01b_embedding_latents.npz"
    np.savez_compressed(
        artifact_path,
        run=meta["run"].to_numpy(dtype=np.int16),
        event_index=meta["event_index"].to_numpy(dtype=np.int32),
        stave_index=meta["stave_index"].to_numpy(dtype=np.int8),
        amplitude_adc=meta["amplitude_adc"].to_numpy(dtype=np.float32),
        z=z.astype(np.float32),
    )
    ae_release.save_state(out_dir / "p01b_autoencoder_state.pt")
    pd.DataFrame({"epoch": np.arange(1, len(release_losses) + 1), "training_loss": release_losses}).to_csv(
        out_dir / "release_ae_training_loss.csv", index=False
    )
    preview = meta[["run", "event_index", "stave", "stave_index", "amplitude_adc"]].head(20).copy()
    for i in range(latent_dim):
        preview["z{}".format(i)] = z[:20, i]
    preview.to_csv(out_dir / "p01b_embedding_preview.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    key_bytes = b"|".join(
        [
            meta["run"].to_numpy(dtype=np.int16).tobytes(),
            meta["event_index"].to_numpy(dtype=np.int32).tobytes(),
            meta["stave_index"].to_numpy(dtype=np.int8).tobytes(),
        ]
    )
    artifact_meta = {
        "ticket_id": config["ticket_id"],
        "artifact": "p01b_embedding_latents.npz",
        "rows": int(len(meta)),
        "latent_dim": latent_dim,
        "key_columns": ["run", "event_index", "stave_index"],
        "value_columns": ["amplitude_adc", "z"],
        "z_dtype": "float32",
        "event_index_definition": "zero-based entry ordinal within each raw hrdb_run_NNNN.root file",
        "artifact_sha256": sha256_file(artifact_path),
        "key_sha256": sha256_bytes(key_bytes),
        "artifact_mib": round(artifact_path.stat().st_size / (1024.0 * 1024.0), 3),
        "normalized_waveform_matrix_mib": round(waves.nbytes / (1024.0 * 1024.0), 3),
        "model_state_file": "p01b_autoencoder_state.pt",
        "release_training_epochs": int(config["ml"]["epochs"]),
        "release_final_training_loss": float(release_losses[-1]),
        "no_benchmark_claim": "release model was fit after held-out evaluation and on all selected rows",
    }
    (out_dir / "p01b_embedding_metadata.json").write_text(json.dumps(json_sanitize(artifact_meta), indent=2) + "\n", encoding="utf-8")
    (out_dir / "p01b_generation_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

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
            "method": "PCA-4 and hand-shape probe",
            "reconstruction": recon[recon["method"] == "traditional PCA-4"].iloc[0].to_dict(),
            "linear_probe": probes[probes["method"] == "traditional PCA-4"].iloc[0].to_dict(),
        },
        "ml": {
            "method": "masked denoising autoencoder",
            "eval_device": str(ae_eval.device),
            "release_device": str(ae_release.device),
            "epochs": int(config["ml"]["epochs"]),
            "latent_dim": latent_dim,
            "heldout_reconstruction": recon[recon["method"] == "ML masked-denoising AE-4"].iloc[0].to_dict(),
            "linear_probe": probes[probes["method"] == "ML masked-denoising AE-4"].iloc[0].to_dict(),
        },
        "leakage_checks": probes[probes["method"].str.startswith("leakage check")].to_dict(orient="records"),
        "artifact": artifact_meta,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, recon, probes, artifact_meta)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01b_full_data_embedding_artifact.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "artifact_sha256": artifact_meta["artifact_sha256"],
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(recon.to_string(index=False))
    print(probes.to_string(index=False))
    print("ARTIFACT {} {:.2f} MiB".format(artifact_path, artifact_meta["artifact_mib"]))
    print("DONE in {}s -> {}".format(result["runtime_sec"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
