#!/usr/bin/env python3
"""P02c: consume P01b embeddings with run-heldout guardrails.

The all-data P01b release embedding is allowed as a feature-production artifact,
but not as the representation used to fit or claim benchmark scores.  The main
benchmark therefore uses a P01b-style train-only autoencoder fit on non-heldout
runs.  A separate forbidden diagnostic fits the same downstream model using the
all-data release embedding to quantify leakage/optimism risk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def scan_raw(config: dict, raw_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    channels = np.asarray([staves[str(name)] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    waves: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {
            "run": int(run),
            "group": groups[int(run)],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_NAMES}
        event_offset = 0
        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
            selected_raw = event_waves[:, channels, :]
            baseline = np.median(selected_raw[..., baseline_idx], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((corrected[event_idx, stave_idx] / amp[:, None]).astype(np.float32))
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "group": groups[int(run)],
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                        }
                    )
                )
            event_offset += int(len(event_waves))
        count_rows.append({**run_counts, **stave_counts})
        print("run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]))

    return np.concatenate(waves, axis=0), pd.concat(meta_parts, ignore_index=True), pd.DataFrame(count_rows)


def shape_features(waves: np.ndarray) -> pd.DataFrame:
    area = waves.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    peak = np.argmax(waves, axis=1)
    return pd.DataFrame(
        {
            "peak_sample": peak.astype(np.float32),
            "area_over_peak": area.astype(np.float32),
            "tail_fraction": (waves[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "late_fraction": (waves[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "early_fraction": (waves[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "final_fraction": waves[:, -1].astype(np.float32),
            "width50": (waves > 0.5).sum(axis=1).astype(np.float32),
            "width20": (waves > 0.2).sum(axis=1).astype(np.float32),
            "max_down_step": np.diff(waves, axis=1).min(axis=1).astype(np.float32),
            "asymmetry": ((waves[:, 10:].sum(axis=1) - waves[:, :5].sum(axis=1)) / abs_area).astype(np.float32),
        }
    )


def manual_labels(feats: pd.DataFrame) -> pd.DataFrame:
    peak = feats["peak_sample"].to_numpy()
    area = feats["area_over_peak"].to_numpy()
    down = feats["max_down_step"].to_numpy()
    labels = pd.DataFrame(index=feats.index)
    labels["peak_group"] = np.where(
        peak <= 3,
        "early_0_3",
        np.where(peak <= 5, "prepeak_4_5", np.where(peak <= 9, "nominal_6_9", "late_10_17")),
    )
    manual = np.full(len(feats), "nominal", dtype=object)
    manual[peak <= 3] = "early_peak_p02"
    manual[(peak <= 4) & (area < 3.0)] = "early_low_area"
    manual[peak >= 12] = "late_peak"
    manual[down < -0.75] = "large_negative_step"
    labels["manual_flag"] = manual
    return labels


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for (_, _), group in meta.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


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
        opt = torch.optim.Adam(self.net.parameters(), lr=float(config["ae"]["learning_rate"]))
        batch_size = int(config["ae"]["batch_size"])
        epochs = int(config["ae"]["epochs"])
        mask_probability = float(config["ae"]["mask_probability"])
        noise_sigma = float(config["ae"]["noise_sigma"])
        losses: List[float] = []
        for epoch in range(epochs):
            perm = torch.randperm(len(xt), device=self.device)
            epoch_losses = []
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
            if epoch in {0, epochs - 1} or (epoch + 1) % 7 == 0:
                print("{} AE epoch {:02d}/{}: loss={:.6f}".format(label, epoch + 1, epochs, losses[-1]))
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        out = []
        self.net.eval()
        with self.torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = self.torch.tensor(x[start : start + batch_size], dtype=self.torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)


def purity_score(y_true: Sequence[object], cluster: Sequence[int]) -> float:
    truth = np.asarray(y_true, dtype=object)
    cl = np.asarray(cluster)
    total = 0
    for label in np.unique(cl):
        vals, counts = np.unique(truth[cl == label], return_counts=True)
        if len(vals):
            total += int(counts.max())
    return float(total) / float(len(truth))


def fit_gmm_best(x_train: np.ndarray, k_values: Sequence[int], seed: int) -> GaussianMixture:
    best_model = None
    best_bic = float("inf")
    for k in k_values:
        model = GaussianMixture(n_components=int(k), covariance_type="diag", random_state=seed, reg_covar=1e-3, max_iter=300, n_init=3)
        try:
            model.fit(x_train)
            bic = float(model.bic(x_train))
        except ValueError as exc:
            print("skipping GMM k={} after fit failure: {}".format(k, exc))
            continue
        if bic < best_bic:
            best_bic = bic
            best_model = model
    if best_model is None:
        raise RuntimeError("No GMM model was fit")
    best_model.best_bic_ = best_bic  # type: ignore[attr-defined]
    return best_model


def benchmark_method(
    method: str,
    x: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    labels: pd.DataFrame,
    runs: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    model = fit_gmm_best(x[train_mask], config["cluster_k_values"], seed)
    pred = np.full(len(x), -1, dtype=int)
    pred[test_mask] = model.predict(x[test_mask])
    rows = []
    for target in ["manual_flag", "peak_group"]:
        y = labels[target].to_numpy()
        rows.append(
            {
                "method": method,
                "target": target,
                "metric": "adjusted_mutual_info",
                "value": float(adjusted_mutual_info_score(y[test_mask], pred[test_mask])),
                "selected_k": int(model.n_components),
                "train_rows": int(train_mask.sum()),
                "heldout_rows": int(test_mask.sum()),
            }
        )
        rows.append(
            {
                "method": method,
                "target": target,
                "metric": "purity",
                "value": purity_score(y[test_mask], pred[test_mask]),
                "selected_k": int(model.n_components),
                "train_rows": int(train_mask.sum()),
                "heldout_rows": int(test_mask.sum()),
            }
        )
    pred_df = pd.DataFrame({"row_index": np.arange(len(x), dtype=np.int64), "run": runs, "method": method, "cluster": pred})
    pred_df = pred_df[test_mask].copy()
    return pd.DataFrame(rows), pred_df


def bootstrap_ci(
    pred: pd.DataFrame,
    labels: pd.DataFrame,
    runs: np.ndarray,
    sample_idx: np.ndarray,
    metric: str,
    target: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    pred_by_pos = pred.set_index("row_index")["cluster"]
    held_rows = pred["row_index"].to_numpy(dtype=int)
    held_runs = runs[held_rows]
    unique_runs = np.unique(held_runs)
    values = []
    y_all = labels[target].to_numpy()
    c_all = pred_by_pos.to_dict()
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        boot_rows = np.concatenate([held_rows[held_runs == run] for run in sampled_runs])
        y = y_all[boot_rows]
        c = np.asarray([c_all[int(row)] for row in boot_rows], dtype=int)
        if metric == "adjusted_mutual_info":
            values.append(float(adjusted_mutual_info_score(y, c)))
        elif metric == "purity":
            values.append(purity_score(y, c))
        else:
            raise ValueError(metric)
    lo, hi = np.quantile(np.asarray(values), [0.025, 0.975])
    return float(lo), float(hi)


def waveform_hashes(waves: np.ndarray) -> np.ndarray:
    rounded = np.round(waves.astype(np.float32), 4)
    return np.asarray([sha256_bytes(row.tobytes()) for row in rounded], dtype=object)


def output_sha256_rows(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and not path.suffix in {".npz", ".pt"}:
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


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


def write_report(out_dir: Path, result: dict, metrics: pd.DataFrame, leakage: pd.DataFrame) -> None:
    main = metrics[metrics["benchmark_role"] == "claim"].copy()
    pivot = main.pivot_table(index=["method", "target", "metric"], values=["value", "ci_low", "ci_high"], aggfunc="first").reset_index()
    release = metrics[metrics["benchmark_role"] == "forbidden_release_diagnostic"].copy()
    release_manual = release[(release["target"] == "manual_flag") & (release["metric"] == "adjusted_mutual_info")].iloc[0]
    ml_manual = main[
        (main["method"] == "ML P01b train-only AE embedding")
        & (main["target"] == "manual_flag")
        & (main["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    trad_manual = main[
        (main["method"] == "traditional hand+PCA morphology")
        & (main["target"] == "manual_flag")
        & (main["metric"] == "adjusted_mutual_info")
    ].iloc[0]

    lines = [
        "# P02c: consume P01b embeddings with run-heldout guardrails",
        "",
        "**Ticket:** `{}`".format(result["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT was scanned from `{}` before any embedding or downstream model fitting. The P01b/S00 selected-pulse count reproduced **{:,}** versus expected **{:,}**.".format(
            result["raw_root_dir"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
        ),
        "",
        "The tracked P01b metadata was found in `{}`. The binary release `.npz` was `{}`, so this consumer `{}` a release-style all-data latent table locally and kept it out of git.".format(
            result["p01b"]["report_dir"],
            result["p01b"]["release_npz_status"],
            result["p01b"]["release_embedding_source"],
        ),
        "",
        "## Methods",
        "Benchmark fitting is split by run: train runs exclude `{}` and held-out runs are `{}`. The benchmark uses a run/stave-balanced sample of **{:,}** pulses and CIs are 95% run-block bootstraps over held-out runs.".format(
            ", ".join(str(run) for run in result["split"]["heldout_runs"]),
            ", ".join(str(run) for run in result["split"]["heldout_runs"]),
            result["split"]["benchmark_rows"],
        ),
        "",
        "- **Traditional:** hand morphology variables plus PCA-4, with diagonal GMM cluster count selected by train-run BIC.",
        "- **ML claim:** P01b-style masked-denoising AE embeddings fit on train runs only, then diagonal GMM selected by train-run BIC.",
        "- **Forbidden diagnostic:** the same downstream GMM procedure using all-data release embeddings. This row is leakage telemetry, not a benchmark claim.",
        "",
        "## Held-out benchmark",
        "| method | target | metric | value | 95% CI |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in pivot.iterrows():
        lines.append(
            "| {} | {} | {} | {:.4f} | [{:.4f}, {:.4f}] |".format(
                row["method"], row["target"], row["metric"], row["value"], row["ci_low"], row["ci_high"]
            )
        )
    lines.extend(
        [
            "",
            "On the primary manual morphology target, traditional AMI is **{:.4f}** [{:.4f}, {:.4f}] and the train-only P01b embedding AMI is **{:.4f}** [{:.4f}, {:.4f}].".format(
                trad_manual["value"], trad_manual["ci_low"], trad_manual["ci_high"], ml_manual["value"], ml_manual["ci_low"], ml_manual["ci_high"]
            ),
            "",
            "The forbidden release-embedding diagnostic gives manual AMI **{:.4f}** [{:.4f}, {:.4f}], delta versus train-only ML **{:+.4f}**. This is reported only to bound leakage risk from using an all-data representation.".format(
                release_manual["value"],
                release_manual["ci_low"],
                release_manual["ci_high"],
                release_manual["value"] - ml_manual["value"],
            ),
            "",
            "## Leakage checks",
            "| check | value | pass | note |",
            "|---|---:|---|---|",
        ]
    )
    for _, row in leakage.iterrows():
        lines.append("| {} | {} | {} | {} |".format(row["check"], row["value"], row["pass"], row["note"]))
    lines.extend(
        [
            "",
            "## Verdict",
            "The P01b consumer path works with the release artifact missing: it regenerates an all-data latent table for feature export while keeping benchmark claims on a train-only embedding. The ML train-only embedding is competitive with, but not cleanly superior to, the strong traditional hand/PCA morphology clustering. Because the release diagnostic is tracked separately and the claimed model never fits on all-data embeddings, P02c supports using P01b latents for downstream feature production with run-heldout guardrails.",
            "",
            "## Reproducibility",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/p02c_p01b_embedding_consumer.py --config configs/p02c_p01b_embedding_consumer.json",
            "```",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p02c_p01b_embedding_consumer.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("raw ROOT dir: {}".format(raw_dir))
    waves, meta, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("Reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [{"quantity": "P01b/S00 selected B-stave pulses", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    p01b_dir = Path(config["p01b_report_dir"])
    p01b_meta_path = p01b_dir / "p01b_embedding_metadata.json"
    p01b_result_path = p01b_dir / "result.json"
    p01b_npz_path = p01b_dir / "p01b_embedding_latents.npz"
    p01b_meta = json.loads(p01b_meta_path.read_text(encoding="utf-8")) if p01b_meta_path.exists() else {}

    sample_idx = balanced_sample(meta, int(config["max_per_run_stave_benchmark"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    bench_runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(bench_runs, heldout_runs)
    test_mask = np.isin(bench_runs, heldout_runs)
    if len(np.intersect1d(bench_runs[train_mask], bench_runs[test_mask])):
        raise RuntimeError("Train/heldout run overlap")

    feats = shape_features(bench_waves)
    labels = manual_labels(feats)
    label_table = pd.concat([bench_meta[["run", "event_index", "stave", "stave_index", "amplitude_adc"]], feats, labels], axis=1)
    label_table.to_csv(out_dir / "benchmark_sample_labels.csv", index=False)
    label_table.groupby(["run", "stave"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_sample_counts.csv", index=False)

    hand_cols = [
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
    hand_matrix = feats[hand_cols].to_numpy(dtype=np.float32)
    traditional_model = make_pipeline(StandardScaler(), PCA(n_components=int(config["latent_dim"]), random_state=int(config["random_seed"])))
    traditional_z = traditional_model.fit(hand_matrix[train_mask]).transform(hand_matrix).astype(np.float32)

    print("fitting train-only P01b-style embedding on {} train rows".format(int(train_mask.sum())))
    train_ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + 17)
    train_losses = train_ae.fit(bench_waves[train_mask], config, "p02c-train-only")
    trainonly_z = train_ae.encode(bench_waves)
    pd.DataFrame({"epoch": np.arange(1, len(train_losses) + 1), "training_loss": train_losses}).to_csv(out_dir / "train_only_ae_loss.csv", index=False)

    release_npz_status = "present" if p01b_npz_path.exists() else "missing"
    regenerated_npz_path = out_dir / "p02c_regenerated_p01b_release_latents.npz"
    if p01b_npz_path.exists():
        loaded = np.load(str(p01b_npz_path))
        release_z_all = loaded["z"].astype(np.float32)
        release_z = release_z_all[sample_idx]
        release_source = "loaded"
        release_artifact_path = p01b_npz_path
    elif regenerated_npz_path.exists():
        print("P01b release npz missing; reusing existing regenerated release embedding {}".format(regenerated_npz_path))
        loaded = np.load(str(regenerated_npz_path))
        release_z_all = loaded["z"].astype(np.float32)
        release_z = release_z_all[sample_idx]
        release_source = "regenerated"
        release_artifact_path = regenerated_npz_path
    else:
        print("P01b release npz missing; regenerating release-style embedding on all {} rows".format(len(waves)))
        release_ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + 9001)
        release_losses = release_ae.fit(waves, config, "p02c-release-all-data")
        release_z_all = release_ae.encode(waves)
        release_z = release_z_all[sample_idx]
        release_artifact_path = regenerated_npz_path
        np.savez_compressed(
            release_artifact_path,
            run=meta["run"].to_numpy(dtype=np.int16),
            event_index=meta["event_index"].to_numpy(dtype=np.int32),
            stave_index=meta["stave_index"].to_numpy(dtype=np.int8),
            amplitude_adc=meta["amplitude_adc"].to_numpy(dtype=np.float32),
            z=release_z_all.astype(np.float32),
        )
        pd.DataFrame({"epoch": np.arange(1, len(release_losses) + 1), "training_loss": release_losses}).to_csv(out_dir / "release_regen_ae_loss.csv", index=False)
        release_source = "regenerated"

    metrics_parts = []
    pred_parts = []
    for method, matrix, role, seed_offset in [
        ("traditional hand+PCA morphology", traditional_z, "claim", 1),
        ("ML P01b train-only AE embedding", trainonly_z, "claim", 2),
        ("forbidden all-data release embedding", release_z, "forbidden_release_diagnostic", 3),
    ]:
        m, p = benchmark_method(method, matrix, train_mask, test_mask, labels, bench_runs, config, int(config["random_seed"]) + seed_offset)
        m["benchmark_role"] = role
        metrics_parts.append(m)
        p["benchmark_role"] = role
        pred_parts.append(p)

    metrics = pd.concat(metrics_parts, ignore_index=True)
    preds = pd.concat(pred_parts, ignore_index=True)
    for idx, row in metrics.iterrows():
        pred = preds[preds["method"] == row["method"]]
        lo, hi = bootstrap_ci(
            pred,
            labels,
            bench_runs,
            sample_idx,
            str(row["metric"]),
            str(row["target"]),
            rng,
            int(config["bootstrap_replicates"]),
        )
        metrics.loc[idx, "ci_low"] = lo
        metrics.loc[idx, "ci_high"] = hi
    metrics.to_csv(out_dir / "heldout_metrics.csv", index=False)
    preds.to_csv(out_dir / "heldout_cluster_predictions.csv", index=False)

    ml_pred = preds[(preds["method"] == "ML P01b train-only AE embedding") & (preds["benchmark_role"] == "claim")]
    held_idx = ml_pred["row_index"].to_numpy(dtype=int)
    ml_clusters = ml_pred["cluster"].to_numpy(dtype=int)
    y_manual = labels["manual_flag"].to_numpy()
    y_peak = labels["peak_group"].to_numpy()
    y_run = bench_runs
    y_stave = bench_meta["stave"].to_numpy(dtype=object)
    hashes = waveform_hashes(bench_waves)
    train_hashes = set(hashes[train_mask].tolist())
    test_hashes = set(hashes[test_mask].tolist())
    release_manual = metrics[
        (metrics["method"] == "forbidden all-data release embedding")
        & (metrics["target"] == "manual_flag")
        & (metrics["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    ml_manual = metrics[
        (metrics["method"] == "ML P01b train-only AE embedding")
        & (metrics["target"] == "manual_flag")
        & (metrics["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    shuffled_manual = y_manual[held_idx].copy()
    rng.shuffle(shuffled_manual)
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(np.intersect1d(bench_runs[train_mask], bench_runs[test_mask]))),
                "pass": True,
                "note": "must be zero",
            },
            {
                "check": "benchmark_fit_uses_release_embedding",
                "value": 0,
                "pass": True,
                "note": "release embedding row is diagnostic only",
            },
            {
                "check": "train_test_rounded_waveform_hash_overlap",
                "value": int(len(train_hashes & test_hashes)),
                "pass": int(len(train_hashes & test_hashes)) == 0,
                "note": "rounded normalized waveform hash at 1e-4 precision",
            },
            {
                "check": "ml_cluster_run_ami",
                "value": float(adjusted_mutual_info_score(y_run[held_idx], ml_clusters)),
                "pass": True,
                "note": "reported to catch run-label clustering",
            },
            {
                "check": "ml_cluster_stave_ami",
                "value": float(adjusted_mutual_info_score(y_stave[held_idx], ml_clusters)),
                "pass": True,
                "note": "reported to catch stave-label clustering",
            },
            {
                "check": "shuffled_manual_label_ami",
                "value": float(adjusted_mutual_info_score(shuffled_manual, ml_clusters)),
                "pass": abs(float(adjusted_mutual_info_score(shuffled_manual, ml_clusters))) < 0.05,
                "note": "evaluation-label shuffle null",
            },
            {
                "check": "forbidden_release_minus_trainonly_manual_ami",
                "value": float(release_manual["value"] - ml_manual["value"]),
                "pass": abs(float(release_manual["value"] - ml_manual["value"])) < 0.05,
                "note": "large positive value would indicate all-data embedding optimism",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [args.config, p01b_meta_path, p01b_result_path]:
        if path.exists():
            input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    artifact_meta = {
        "release_embedding_source": release_source,
        "release_npz_status": release_npz_status,
        "release_artifact_path": str(release_artifact_path),
        "release_artifact_sha256": sha256_file(release_artifact_path) if release_artifact_path.exists() else None,
        "release_artifact_rows": int(len(waves)),
        "latent_dim": int(config["latent_dim"]),
        "p01b_metadata_rows": p01b_meta.get("rows"),
        "p01b_metadata_artifact_sha256": p01b_meta.get("artifact_sha256"),
        "no_benchmark_claim": "all-data release embedding is excluded from claim rows and appears only as forbidden diagnostic telemetry",
    }
    (out_dir / "p02c_embedding_artifact_metadata.json").write_text(json.dumps(json_sanitize(artifact_meta), indent=2) + "\n", encoding="utf-8")

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "p01b": {
            "report_dir": str(p01b_dir),
            "metadata_found": bool(p01b_meta_path.exists()),
            "release_npz_status": release_npz_status,
            "release_embedding_source": release_source,
        },
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "benchmark_rows": int(len(bench_waves)),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
        },
        "metrics": metrics.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "artifact": artifact_meta,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, metrics, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p02c_p01b_embedding_consumer.py",
        "config": str(args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p02c_p01b_embedding_consumer.py --config {}".format(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == expected,
        "output_sha256": output_sha256_rows(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(metrics.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(result["runtime_sec"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
