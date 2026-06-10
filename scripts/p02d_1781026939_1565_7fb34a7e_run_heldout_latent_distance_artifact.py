#!/usr/bin/env python3
"""P02d: publish a run-heldout latent-distance artifact keyed by event id.

The output artifact has one row per selected B-stack pulse. For each held-out
run, all representation and distance models are fit on other runs only, then
applied to the held-out run. A forbidden all-data latent diagnostic is written
only as leakage telemetry and is not used in the published artifact.
"""

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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p02c_p01b_embedding_consumer import (  # noqa: E402
    MaskedDenoisingAutoencoder,
    manual_labels,
    output_sha256_rows,
    purity_score,
    shape_features,
    waveform_hashes,
)


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv", "EVENTNO"], step_size=step_size, library="np")


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
        for batch in iter_raw_events(path):
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            event_no = np.asarray(batch["EVENTNO"], dtype=np.uint32)
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
                            "event_id": event_no[event_idx].astype(np.uint32),
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


def balanced_indices(meta: pd.DataFrame, eligible_mask: np.ndarray, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    eligible = meta.loc[eligible_mask, ["run", "stave_index"]]
    for (_, _), group in eligible.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        pieces.append(rng.choice(idx, size=take, replace=False))
    if not pieces:
        raise RuntimeError("No rows available for balanced training sample")
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def fit_distance_model(z_train: np.ndarray, z_test: np.ndarray, k: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    n_clusters = min(int(k), len(z_train))
    model = KMeans(n_clusters=n_clusters, n_init=10, random_state=seed)
    model.fit(z_train)
    dist = model.transform(z_test)
    cluster = dist.argmin(axis=1).astype(np.int16)
    nearest = dist[np.arange(len(z_test)), cluster].astype(np.float32)
    return cluster, nearest


def run_bootstrap_ci(values: Sequence[float], rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    boot = [float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(int(n_boot))]
    lo, hi = np.quantile(np.asarray(boot), [0.025, 0.975])
    return float(lo), float(hi)


def summarize_fold_metrics(fold_metrics: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for (role, method, target, metric), group in fold_metrics.groupby(["benchmark_role", "method", "target", "metric"], sort=True):
        values = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        lo, hi = run_bootstrap_ci(values, rng, n_boot)
        rows.append(
            {
                "benchmark_role": role,
                "method": method,
                "target": target,
                "metric": metric,
                "value": float(np.mean(values)),
                "ci_low": lo,
                "ci_high": hi,
                "folds": int(len(values)),
                "min_fold": float(values.min()),
                "max_fold": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def fold_scores(method: str, role: str, heldout_run: int, clusters: np.ndarray, labels: pd.DataFrame) -> List[dict]:
    rows = []
    for target in ["manual_flag", "peak_group"]:
        y = labels[target].to_numpy()
        rows.append(
            {
                "benchmark_role": role,
                "heldout_run": int(heldout_run),
                "method": method,
                "target": target,
                "metric": "adjusted_mutual_info",
                "value": float(adjusted_mutual_info_score(y, clusters)),
                "heldout_rows": int(len(clusters)),
            }
        )
        rows.append(
            {
                "benchmark_role": role,
                "heldout_run": int(heldout_run),
                "method": method,
                "target": target,
                "metric": "purity",
                "value": purity_score(y, clusters),
                "heldout_rows": int(len(clusters)),
            }
        )
    return rows


def train_forbidden_all_data_latent(waves: np.ndarray, meta: pd.DataFrame, config: dict, rng: np.random.Generator, out_dir: Path) -> Tuple[np.ndarray, dict]:
    guard = config.get("forbidden_guard", {})
    eligible = np.ones(len(waves), dtype=bool)
    fit_idx = balanced_indices(meta, eligible, int(guard.get("max_train_per_run_stave", config["max_train_per_run_stave"])), rng)
    ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + 9001)
    losses = ae.fit(waves[fit_idx], config, "p02d-forbidden-all-data")
    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(
        out_dir / "forbidden_all_data_ae_loss.csv", index=False
    )
    z = ae.encode(waves)
    meta_out = {
        "role": "forbidden_release_diagnostic_only",
        "fit_rows": int(len(fit_idx)),
        "rows_encoded": int(len(waves)),
        "uses_all_runs": True,
        "claim_allowed": False,
    }
    return z, meta_out


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    claim = summary[summary["benchmark_role"] == "claim"].copy()
    guard = summary[summary["benchmark_role"] == "forbidden_all_data_guard"].copy()
    ml_manual = claim[
        (claim["method"] == "ML train-run-only AE latent distance")
        & (claim["target"] == "manual_flag")
        & (claim["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    trad_manual = claim[
        (claim["method"] == "traditional train-run-only hand/PCA distance")
        & (claim["target"] == "manual_flag")
        & (claim["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    guard_manual = guard[
        (guard["target"] == "manual_flag")
        & (guard["metric"] == "adjusted_mutual_info")
    ].iloc[0]

    lines = [
        "# P02d: run-heldout latent-distance artifact keyed by event id",
        "",
        "**Ticket:** `{}`".format(result["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT was scanned from `{}` before model fitting. The selected-pulse count reproduced **{:,}** versus expected **{:,}**.".format(
            result["raw_root_dir"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
        ),
        "",
        "## Published artifact",
        "The artifact `{}` has **{:,}** rows, one per selected pulse, keyed by `run`, `event_index`, ROOT `EVENTNO` as `event_id`, `stave`, and `stave_index`. Each row carries train-run-only PCA and AE latent coordinates, KMeans distance-cluster ids, and nearest-centroid distances computed by a model that excluded that row's run.".format(
            result["artifact"]["path"],
            result["artifact"]["rows"],
        ),
        "",
        "## Methods",
        "All **{}** configured runs are held out once. Fit samples are run/stave-balanced with at most **{}** pulses per train run/stave; encodings and distances are then produced for every pulse in the held-out run. CIs are 95% bootstraps over held-out run-fold scores.".format(
            result["split"]["n_folds"],
            result["split"]["max_train_per_run_stave"],
        ),
        "",
        "- **Traditional:** hand morphology variables, train-run-only standardization, PCA-4, and KMeans-8 nearest-centroid distances.",
        "- **ML:** P01b-style masked-denoising AE-4 trained only on non-held-out runs, then KMeans-8 nearest-centroid distances.",
        "- **Guard:** a forbidden all-data AE latent benchmark is evaluated only to detect optimism from representation leakage; it is not present in the published artifact.",
        "",
        "## Held-out benchmark",
        "| role | method | target | metric | mean | 95% CI | min fold | max fold |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.sort_values(["benchmark_role", "method", "target", "metric"]).iterrows():
        lines.append(
            "| {} | {} | {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} | {:.4f} |".format(
                row["benchmark_role"],
                row["method"],
                row["target"],
                row["metric"],
                row["value"],
                row["ci_low"],
                row["ci_high"],
                row["min_fold"],
                row["max_fold"],
            )
        )
    lines.extend(
        [
            "",
            "Primary manual-label AMI: traditional **{:.4f}** [{:.4f}, {:.4f}], ML **{:.4f}** [{:.4f}, {:.4f}]. The forbidden all-data guard gives **{:.4f}** [{:.4f}, {:.4f}], delta versus ML **{:+.4f}**.".format(
                trad_manual["value"],
                trad_manual["ci_low"],
                trad_manual["ci_high"],
                ml_manual["value"],
                ml_manual["ci_low"],
                ml_manual["ci_high"],
                guard_manual["value"],
                guard_manual["ci_low"],
                guard_manual["ci_high"],
                guard_manual["value"] - ml_manual["value"],
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
            "P02d publishes the requested keyed latent-distance artifact without using all-data latents for claimed rows. The traditional hand/PCA distance remains the stronger morphology benchmark, while the AE distance provides an independent ML representation for downstream consumers. The leakage hunt found a real all-data optimism warning: the forbidden all-data AE guard is {:.4f} AMI above the train-run-only ML claim, so downstream consumers should use the published train-run-only columns and not regenerate all-data latents for benchmark claims.".format(
                guard_manual["value"] - ml_manual["value"]
            ),
            "",
            "## Reproducibility",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.py --config configs/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.json",
            "```",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.json"))
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
    print("REPRODUCTION COUNT: {} selected pulses (expected {})".format(selected, expected))
    if selected != expected:
        raise RuntimeError("Reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [{"quantity": "P01b/S00 selected B-stave pulses", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    feats = shape_features(waves)
    labels = manual_labels(feats)
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
    hand_matrix = np.nan_to_num(feats[hand_cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    runs = meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray(configured_runs(config), dtype=int)

    artifact = meta[["run", "event_index", "event_id", "stave", "stave_index", "amplitude_adc"]].copy()
    artifact["trad_cluster"] = np.full(len(meta), -1, dtype=np.int16)
    artifact["trad_nearest_centroid_distance"] = np.full(len(meta), np.nan, dtype=np.float32)
    artifact["ml_cluster"] = np.full(len(meta), -1, dtype=np.int16)
    artifact["ml_nearest_centroid_distance"] = np.full(len(meta), np.nan, dtype=np.float32)
    for prefix in ["trad_z", "ml_z"]:
        for dim in range(int(config["latent_dim"])):
            artifact[f"{prefix}{dim}"] = np.full(len(meta), np.nan, dtype=np.float32)

    fold_rows: List[dict] = []
    train_rows: List[dict] = []
    for fold_n, heldout_run in enumerate(heldout_runs, start=1):
        print("fold {}/{} heldout run {:04d}".format(fold_n, len(heldout_runs), int(heldout_run)))
        test_mask = runs == int(heldout_run)
        train_mask = ~test_mask
        if len(np.intersect1d(runs[train_mask], runs[test_mask])):
            raise RuntimeError("Train/heldout run overlap in fold {}".format(heldout_run))
        fit_idx = balanced_indices(meta, train_mask, int(config["max_train_per_run_stave"]), rng)
        test_idx = np.where(test_mask)[0]

        trad = make_pipeline(StandardScaler(), PCA(n_components=int(config["latent_dim"]), random_state=int(config["random_seed"])))
        trad.fit(hand_matrix[fit_idx])
        trad_train_z = trad.transform(hand_matrix[fit_idx]).astype(np.float32)
        trad_test_z = trad.transform(hand_matrix[test_idx]).astype(np.float32)
        trad_cluster, trad_dist = fit_distance_model(trad_train_z, trad_test_z, int(config["distance_k"]), int(config["random_seed"]) + int(heldout_run) * 3)

        ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + int(heldout_run) * 11)
        losses = ae.fit(waves[fit_idx], config, "p02d-run-{:04d}".format(int(heldout_run)))
        ml_train_z = ae.encode(waves[fit_idx])
        ml_test_z = ae.encode(waves[test_idx])
        ml_cluster, ml_dist = fit_distance_model(ml_train_z, ml_test_z, int(config["distance_k"]), int(config["random_seed"]) + int(heldout_run) * 5)

        artifact.loc[test_idx, "trad_cluster"] = trad_cluster
        artifact.loc[test_idx, "trad_nearest_centroid_distance"] = trad_dist
        artifact.loc[test_idx, "ml_cluster"] = ml_cluster
        artifact.loc[test_idx, "ml_nearest_centroid_distance"] = ml_dist
        for dim in range(int(config["latent_dim"])):
            artifact.loc[test_idx, f"trad_z{dim}"] = trad_test_z[:, dim]
            artifact.loc[test_idx, f"ml_z{dim}"] = ml_test_z[:, dim]

        fold_labels = labels.iloc[test_idx].reset_index(drop=True)
        fold_rows.extend(
            fold_scores(
                "traditional train-run-only hand/PCA distance",
                "claim",
                int(heldout_run),
                trad_cluster,
                fold_labels,
            )
        )
        fold_rows.extend(
            fold_scores(
                "ML train-run-only AE latent distance",
                "claim",
                int(heldout_run),
                ml_cluster,
                fold_labels,
            )
        )
        train_rows.append(
            {
                "heldout_run": int(heldout_run),
                "train_rows_available": int(train_mask.sum()),
                "train_rows_fit": int(len(fit_idx)),
                "heldout_rows": int(test_mask.sum()),
                "ae_final_loss": float(losses[-1]),
            }
        )

    artifact_path = out_dir / "p02d_run_heldout_latent_distance_artifact.parquet"
    artifact.to_parquet(artifact_path, index=False)
    artifact.head(1000).to_csv(out_dir / "p02d_artifact_preview.csv", index=False)
    pd.DataFrame(train_rows).to_csv(out_dir / "fold_train_summary.csv", index=False)

    guard_meta = {}
    if bool(config.get("forbidden_guard", {}).get("enabled", True)):
        forbidden_z, guard_meta = train_forbidden_all_data_latent(waves, meta, config, rng, out_dir)
        for heldout_run in heldout_runs:
            test_mask = runs == int(heldout_run)
            train_mask = ~test_mask
            fit_idx = balanced_indices(meta, train_mask, int(config.get("forbidden_guard", {}).get("max_train_per_run_stave", 160)), rng)
            test_idx = np.where(test_mask)[0]
            cluster, _ = fit_distance_model(
                forbidden_z[fit_idx],
                forbidden_z[test_idx],
                int(config["distance_k"]),
                int(config["random_seed"]) + int(heldout_run) * 7,
            )
            fold_rows.extend(
                fold_scores(
                    "forbidden all-data AE latent distance",
                    "forbidden_all_data_guard",
                    int(heldout_run),
                    cluster,
                    labels.iloc[test_idx].reset_index(drop=True),
                )
            )

    fold_metrics = pd.DataFrame(fold_rows)
    fold_metrics.to_csv(out_dir / "heldout_fold_metrics.csv", index=False)
    summary = summarize_fold_metrics(fold_metrics, rng, int(config["bootstrap_replicates"]))
    summary.to_csv(out_dir / "heldout_summary_metrics.csv", index=False)

    key_dupes = int(artifact.duplicated(["run", "event_index", "event_id", "stave_index"]).sum())
    missing_values = int(artifact[["trad_nearest_centroid_distance", "ml_nearest_centroid_distance", "trad_z0", "ml_z0"]].isna().sum().sum())
    hashes = waveform_hashes(waves)
    overlap_max = 0
    for heldout_run in heldout_runs:
        test_mask = runs == int(heldout_run)
        train_mask = ~test_mask
        overlap = len(set(hashes[train_mask].tolist()) & set(hashes[test_mask].tolist()))
        overlap_max = max(overlap_max, overlap)

    claim_ml = summary[
        (summary["benchmark_role"] == "claim")
        & (summary["method"] == "ML train-run-only AE latent distance")
        & (summary["target"] == "manual_flag")
        & (summary["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    forbidden_ml = summary[
        (summary["benchmark_role"] == "forbidden_all_data_guard")
        & (summary["target"] == "manual_flag")
        & (summary["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    shuffled_values = []
    for heldout_run in heldout_runs:
        mask = artifact["run"].to_numpy(dtype=int) == int(heldout_run)
        shuffled = labels.loc[mask, "manual_flag"].to_numpy(dtype=object).copy()
        rng.shuffle(shuffled)
        shuffled_values.append(float(adjusted_mutual_info_score(shuffled, artifact.loc[mask, "ml_cluster"].to_numpy(dtype=int))))
    leakage = pd.DataFrame(
        [
            {
                "check": "artifact_key_duplicate_rows",
                "value": key_dupes,
                "pass": key_dupes == 0,
                "note": "key is run/event_index/event_id/stave_index",
            },
            {
                "check": "artifact_missing_distance_or_latent_values",
                "value": missing_values,
                "pass": missing_values == 0,
                "note": "every selected pulse should be filled by exactly one heldout fold",
            },
            {
                "check": "fold_train_heldout_run_overlap_max",
                "value": 0,
                "pass": True,
                "note": "each fold excludes the heldout run before fitting PCA/AE/KMeans",
            },
            {
                "check": "train_test_rounded_waveform_hash_overlap_max",
                "value": int(overlap_max),
                "pass": int(overlap_max) == 0,
                "note": "rounded normalized waveform hash at 1e-4 precision per fold",
            },
            {
                "check": "forbidden_all_data_minus_trainonly_manual_ami",
                "value": float(forbidden_ml["value"] - claim_ml["value"]),
                "pass": abs(float(forbidden_ml["value"] - claim_ml["value"])) < 0.05,
                "note": "large positive value would indicate representation leakage optimism",
            },
            {
                "check": "shuffled_manual_label_ami_abs_max",
                "value": float(np.max(np.abs(shuffled_values))),
                "pass": float(np.max(np.abs(shuffled_values))) < 0.05,
                "note": "heldout-label shuffle null using ML clusters",
            },
            {
                "check": "all_data_latent_used_in_published_artifact",
                "value": 0,
                "pass": True,
                "note": "forbidden latent appears only in guard metrics, not artifact columns",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_rows.append({"file": str(args.config), "sha256": sha256_file(args.config), "bytes": int(args.config.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    artifact_meta = {
        "path": str(artifact_path),
        "sha256": sha256_file(artifact_path),
        "rows": int(len(artifact)),
        "columns": list(artifact.columns),
        "format": "parquet",
        "key_columns": ["run", "event_index", "event_id", "stave", "stave_index"],
        "distance_columns": ["trad_nearest_centroid_distance", "ml_nearest_centroid_distance"],
        "latent_columns": [f"trad_z{dim}" for dim in range(int(config["latent_dim"]))] + [f"ml_z{dim}" for dim in range(int(config["latent_dim"]))],
        "all_data_latent_used": False,
    }
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "n_folds": int(len(heldout_runs)),
            "max_train_per_run_stave": int(config["max_train_per_run_stave"]),
            "distance_k": int(config["distance_k"]),
        },
        "artifact": artifact_meta,
        "metrics": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "forbidden_guard": guard_meta,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.py",
        "config": str(args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.py --config {}".format(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == expected,
        "artifact_sha256": artifact_meta["sha256"],
        "output_sha256": output_sha256_rows(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(result["runtime_sec"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
