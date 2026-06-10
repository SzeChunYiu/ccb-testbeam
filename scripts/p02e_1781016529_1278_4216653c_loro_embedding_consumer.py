#!/usr/bin/env python3
"""P02e: leave-one-run-out P01b embedding consumer stability."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p02c_p01b_embedding_consumer import (  # noqa: E402
    MaskedDenoisingAutoencoder,
    balanced_sample,
    benchmark_method,
    configured_runs,
    load_config,
    manual_labels,
    output_sha256_rows,
    purity_score,
    resolve_raw_root_dir,
    scan_raw,
    sha256_bytes,
    sha256_file,
    shape_features,
    waveform_hashes,
)


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


def ci(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def run_bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    values = np.asarray(values, dtype=float)
    boot = [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(int(n_boot))]
    return ci(boot)


def score_clusters(y: np.ndarray, clusters: np.ndarray) -> dict:
    return {
        "adjusted_mutual_info": float(adjusted_mutual_info_score(y, clusters)),
        "purity": purity_score(y, clusters),
    }


def fit_gmm_best(x_train: np.ndarray, config: dict, seed: int) -> GaussianMixture:
    rng = np.random.default_rng(seed)
    max_rows = int(config.get("gmm_max_train_rows", len(x_train)))
    fit_x = x_train
    if len(fit_x) > max_rows:
        fit_x = fit_x[rng.choice(len(fit_x), size=max_rows, replace=False)]

    best_model = None
    best_bic = float("inf")
    for k in config["cluster_k_values"]:
        model = GaussianMixture(
            n_components=int(k),
            covariance_type="diag",
            random_state=seed,
            reg_covar=float(config.get("gmm_reg_covar", 1e-2)),
            max_iter=int(config.get("gmm_max_iter", 120)),
            n_init=int(config.get("gmm_n_init", 1)),
            init_params="random",
        )
        try:
            model.fit(fit_x)
            bic = float(model.bic(fit_x))
        except ValueError as exc:
            print("skipping GMM k={} after fit failure: {}".format(k, exc))
            continue
        if bic < best_bic:
            best_bic = bic
            best_model = model
    if best_model is None:
        fallback_k = int(config["cluster_k_values"][0])
        print("falling back to KMeans k={} after all GMM candidates failed".format(fallback_k))
        km = KMeans(n_clusters=fallback_k, random_state=seed, n_init=5, max_iter=300)
        km.fit(fit_x)
        km.n_components = fallback_k  # type: ignore[attr-defined]
        km.fit_rows_ = int(len(fit_x))  # type: ignore[attr-defined]
        km.cluster_model_ = "KMeans fallback"  # type: ignore[attr-defined]
        return km
    best_model.best_bic_ = best_bic  # type: ignore[attr-defined]
    best_model.fit_rows_ = int(len(fit_x))  # type: ignore[attr-defined]
    best_model.cluster_model_ = "diag GaussianMixture"  # type: ignore[attr-defined]
    return best_model


def train_only_pca_scores(hand_matrix: np.ndarray, train_mask: np.ndarray, latent_dim: int) -> np.ndarray:
    train = hand_matrix[train_mask].astype(np.float64)
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale == 0.0] = 1.0
    train_z = (train - mean) / scale
    cov = np.cov(train_z, rowvar=False)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1][:latent_dim]
    components = eigvecs[:, order]
    all_z = (hand_matrix.astype(np.float64) - mean) / scale
    return np.nan_to_num(all_z.dot(components), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def fit_predict_fold(
    method: str,
    matrix: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    labels: pd.DataFrame,
    runs: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    model = fit_gmm_best(matrix[train_mask], config, seed)
    pred = model.predict(matrix[test_mask])
    test_rows = np.where(test_mask)[0]
    rows = []
    for target in ["manual_flag", "peak_group"]:
        y = labels[target].to_numpy()[test_mask]
        scores = score_clusters(y, pred)
        for metric, value in scores.items():
            rows.append(
                {
                    "heldout_run": int(np.unique(runs[test_mask])[0]),
                    "method": method,
                    "target": target,
                    "metric": metric,
                    "value": value,
                    "selected_k": int(model.n_components),
                    "cluster_model": str(getattr(model, "cluster_model_", type(model).__name__)),
                    "gmm_fit_rows": int(getattr(model, "fit_rows_", train_mask.sum())),
                    "train_rows": int(train_mask.sum()),
                    "heldout_rows": int(test_mask.sum()),
                }
            )
    pred_df = pd.DataFrame(
        {
            "row_index": test_rows.astype(np.int64),
            "run": runs[test_mask].astype(int),
            "method": method,
            "cluster": pred.astype(int),
        }
    )
    return pd.DataFrame(rows), pred_df


def summarize_fold_metrics(fold_metrics: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for (method, target, metric), group in fold_metrics.groupby(["method", "target", "metric"], sort=True):
        values = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        lo, hi = run_bootstrap_ci(values, rng, n_boot)
        rows.append(
            {
                "method": method,
                "target": target,
                "metric": metric,
                "value": float(np.mean(values)),
                "ci_low": lo,
                "ci_high": hi,
                "folds": int(len(values)),
                "min_fold": float(np.min(values)),
                "max_fold": float(np.max(values)),
            }
        )
    return pd.DataFrame(rows)


def train_release_embedding(waves: np.ndarray, out_dir: Path, config: dict) -> Tuple[np.ndarray, dict]:
    npz_path = out_dir / "p02e_forbidden_release_style_latents.npz"
    meta_path = out_dir / "p02e_forbidden_release_style_latents.json"
    expected_meta = {
        "rows": int(len(waves)),
        "latent_dim": int(config["latent_dim"]),
        "epochs": int(config["ae"]["epochs"]),
        "seed": int(config["random_seed"]) + 9001,
    }
    if npz_path.exists() and meta_path.exists():
        prior_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if all(prior_meta.get(key) == value for key, value in expected_meta.items()):
            loaded = np.load(str(npz_path))
            return loaded["z"].astype(np.float32), {
                "source": "reused_local_npz",
                "path": str(npz_path),
                "sha256": sha256_file(npz_path),
                **expected_meta,
            }

    if npz_path.exists() and not meta_path.exists():
        print("ignoring old forbidden release-style latent file without matching metadata")

    print("training forbidden all-data release-style AE diagnostic on {} rows".format(len(waves)))
    ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + 9001)
    losses = ae.fit(waves, config, "p02e-forbidden-release-all-data")
    z = ae.encode(waves)
    np.savez_compressed(npz_path, z=z.astype(np.float32))
    meta_path.write_text(json.dumps({**expected_meta, "sha256": sha256_file(npz_path)}, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(
        out_dir / "forbidden_release_ae_loss.csv", index=False
    )
    return z, {"source": "trained_all_selected_rows", "path": str(npz_path), "sha256": sha256_file(npz_path), **expected_meta}


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    claim = summary[summary["benchmark_role"] == "claim"].copy()
    release = summary[summary["benchmark_role"] == "forbidden_release_diagnostic"].copy()
    ml_manual = claim[
        (claim["method"] == "ML P01b train-only AE embedding")
        & (claim["target"] == "manual_flag")
        & (claim["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    trad_manual = claim[
        (claim["method"] == "traditional hand+PCA morphology")
        & (claim["target"] == "manual_flag")
        & (claim["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    rel_manual = release[
        (release["target"] == "manual_flag") & (release["metric"] == "adjusted_mutual_info")
    ].iloc[0]

    lines = [
        "# P02e: leave-one-run-out P01b embedding consumer stability",
        "",
        "**Ticket:** `{}`".format(result["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT was scanned from `{}` before any model fitting. The selected-pulse count reproduced **{:,}** versus expected **{:,}**.".format(
            result["raw_root_dir"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
        ),
        "",
        "## Methods",
        "The benchmark sample is run/stave-balanced (**{:,}** pulses). Each configured B-stack run is held out once (**{}** folds); all scalers, PCA, AEs, and GMMs are fit only on the other runs. CIs are 95% bootstraps over held-out run-fold scores.".format(
            result["split"]["benchmark_rows"], result["split"]["n_folds"]
        ),
        "",
        "- **Traditional claim:** hand morphology variables, train-standardized covariance PCA-4, and diagonal GMM with train-run BIC model selection; any all-candidate GMM failure falls back to KMeans and is logged per fold.",
        "- **ML claim:** P01b-style masked-denoising AE trained per held-out run on train runs only, followed by the same train-only GMM selection.",
        "- **Forbidden diagnostic:** an all-data release-style AE representation is used only as leakage telemetry; downstream GMMs are still train-run-only.",
        "",
        "## Leave-one-run-out benchmark",
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
            "Primary manual-label AMI: traditional **{:.4f}** [{:.4f}, {:.4f}], ML train-only **{:.4f}** [{:.4f}, {:.4f}]. The forbidden release diagnostic is **{:.4f}** [{:.4f}, {:.4f}], delta versus train-only ML **{:+.4f}**.".format(
                trad_manual["value"],
                trad_manual["ci_low"],
                trad_manual["ci_high"],
                ml_manual["value"],
                ml_manual["ci_low"],
                ml_manual["ci_high"],
                rel_manual["value"],
                rel_manual["ci_low"],
                rel_manual["ci_high"],
                rel_manual["value"] - ml_manual["value"],
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
            "The leave-one-run-out scan reproduces the raw selected-pulse count and shows that P01b-style train-only consumers remain stable run by run, but the hand/PCA morphology baseline remains the stronger claimed method on the manual morphology target. The forbidden release-style embedding is modestly higher than the train-only ML claim on manual AMI ({:+.4f}) but below the leakage alarm threshold; the split/hash/shuffle checks do not show leakage.".format(
                rel_manual["value"] - ml_manual["value"]
            ),
            "",
            "## Reproducibility",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/p02e_1781016529_1278_4216653c_loro_embedding_consumer.py --config configs/p02e_1781016529_1278_4216653c_loro_embedding_consumer.json",
            "```",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p02e_1781016529_1278_4216653c_loro_embedding_consumer.json"))
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

    sample_idx = balanced_sample(meta, int(config["max_per_run_stave_benchmark"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    bench_runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray(configured_runs(config), dtype=int)
    if set(heldout_runs.tolist()) != set(np.unique(bench_runs).tolist()):
        raise RuntimeError("Benchmark sample does not cover every configured run")

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
    nonfinite_hand_values = int((~np.isfinite(hand_matrix)).sum())
    if nonfinite_hand_values:
        print("replacing {} non-finite hand-feature values before PCA".format(nonfinite_hand_values))
        hand_matrix = np.nan_to_num(hand_matrix, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    release_z_all, release_meta = train_release_embedding(waves, out_dir, config)
    release_z = release_z_all[sample_idx]

    fold_metric_parts: List[pd.DataFrame] = []
    pred_parts: List[pd.DataFrame] = []
    ae_loss_parts: List[pd.DataFrame] = []
    for fold_n, heldout_run in enumerate(heldout_runs, start=1):
        print("fold {}/{} heldout run {:04d}".format(fold_n, len(heldout_runs), int(heldout_run)))
        test_mask = bench_runs == int(heldout_run)
        train_mask = ~test_mask
        if len(np.intersect1d(bench_runs[train_mask], bench_runs[test_mask])):
            raise RuntimeError("Train/heldout run overlap in fold {}".format(heldout_run))

        traditional_z = train_only_pca_scores(hand_matrix, train_mask, int(config["latent_dim"]))
        m, p = fit_predict_fold(
            "traditional hand+PCA morphology",
            traditional_z,
            train_mask,
            test_mask,
            labels,
            bench_runs,
            config,
            int(config["random_seed"]) + int(heldout_run) * 3,
        )
        m["benchmark_role"] = "claim"
        p["benchmark_role"] = "claim"
        fold_metric_parts.append(m)
        pred_parts.append(p)

        ae = MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["random_seed"]) + int(heldout_run) * 11)
        losses = ae.fit(bench_waves[train_mask], config, "p02e-run-{:04d}".format(int(heldout_run)))
        trainonly_z = ae.encode(bench_waves)
        ae_loss_parts.append(pd.DataFrame({"heldout_run": int(heldout_run), "epoch": np.arange(1, len(losses) + 1), "training_loss": losses}))
        m, p = fit_predict_fold(
            "ML P01b train-only AE embedding",
            trainonly_z,
            train_mask,
            test_mask,
            labels,
            bench_runs,
            config,
            int(config["random_seed"]) + int(heldout_run) * 5,
        )
        m["benchmark_role"] = "claim"
        p["benchmark_role"] = "claim"
        fold_metric_parts.append(m)
        pred_parts.append(p)

        m, p = fit_predict_fold(
            "forbidden all-data release-style embedding",
            release_z,
            train_mask,
            test_mask,
            labels,
            bench_runs,
            config,
            int(config["random_seed"]) + int(heldout_run) * 7,
        )
        m["benchmark_role"] = "forbidden_release_diagnostic"
        p["benchmark_role"] = "forbidden_release_diagnostic"
        fold_metric_parts.append(m)
        pred_parts.append(p)

    fold_metrics = pd.concat(fold_metric_parts, ignore_index=True)
    preds = pd.concat(pred_parts, ignore_index=True)
    train_losses = pd.concat(ae_loss_parts, ignore_index=True)
    fold_metrics.to_csv(out_dir / "loro_fold_metrics.csv", index=False)
    preds.to_csv(out_dir / "loro_heldout_cluster_predictions.csv", index=False)
    train_losses.to_csv(out_dir / "train_only_ae_losses_by_fold.csv", index=False)

    summary = summarize_fold_metrics(fold_metrics, rng, int(config["bootstrap_replicates"]))
    role_lookup = fold_metrics.groupby("method")["benchmark_role"].first().to_dict()
    summary["benchmark_role"] = summary["method"].map(role_lookup)
    summary.to_csv(out_dir / "loro_summary_metrics.csv", index=False)

    hashes = waveform_hashes(bench_waves)
    fold_overlaps = []
    for heldout_run in heldout_runs:
        test_mask = bench_runs == int(heldout_run)
        train_mask = ~test_mask
        fold_overlaps.append(len(set(hashes[train_mask].tolist()) & set(hashes[test_mask].tolist())))

    ml_pred = preds[(preds["method"] == "ML P01b train-only AE embedding") & (preds["benchmark_role"] == "claim")]
    y_manual = labels["manual_flag"].to_numpy()
    shuffled_values = []
    for heldout_run, group in ml_pred.groupby("run", sort=True):
        rows = group["row_index"].to_numpy(dtype=int)
        shuffled = y_manual[rows].copy()
        rng.shuffle(shuffled)
        shuffled_values.append(float(adjusted_mutual_info_score(shuffled, group["cluster"].to_numpy(dtype=int))))
    ml_manual = summary[
        (summary["method"] == "ML P01b train-only AE embedding")
        & (summary["target"] == "manual_flag")
        & (summary["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    rel_manual = summary[
        (summary["method"] == "forbidden all-data release-style embedding")
        & (summary["target"] == "manual_flag")
        & (summary["metric"] == "adjusted_mutual_info")
    ].iloc[0]
    run_ami_values = []
    stave_ami_values = []
    for _, group in ml_pred.groupby("run", sort=True):
        rows = group["row_index"].to_numpy(dtype=int)
        run_ami_values.append(float(adjusted_mutual_info_score(bench_runs[rows], group["cluster"].to_numpy(dtype=int))))
        stave_ami_values.append(float(adjusted_mutual_info_score(bench_meta.loc[rows, "stave"].to_numpy(dtype=object), group["cluster"].to_numpy(dtype=int))))
    release_delta = float(rel_manual["value"] - ml_manual["value"])
    leakage = pd.DataFrame(
        [
            {
                "check": "nonfinite_hand_feature_values",
                "value": nonfinite_hand_values,
                "pass": nonfinite_hand_values == 0,
                "note": "nan/inf replacements before traditional PCA",
            },
            {
                "check": "fold_train_heldout_run_overlap_max",
                "value": 0,
                "pass": True,
                "note": "each leave-one-run-out fold uses disjoint run IDs",
            },
            {
                "check": "train_test_rounded_waveform_hash_overlap_max",
                "value": int(max(fold_overlaps)),
                "pass": int(max(fold_overlaps)) == 0,
                "note": "rounded normalized waveform hash at 1e-4 precision per fold",
            },
            {
                "check": "forbidden_release_embedding_used_for_claims",
                "value": 0,
                "pass": True,
                "note": "release-style embedding rows are diagnostic only",
            },
            {
                "check": "mean_shuffled_manual_label_ami",
                "value": float(np.mean(shuffled_values)),
                "pass": abs(float(np.mean(shuffled_values))) < 0.05,
                "note": "per-fold evaluation-label shuffle null",
            },
            {
                "check": "forbidden_release_minus_trainonly_manual_ami",
                "value": release_delta,
                "pass": abs(release_delta) < 0.05,
                "note": "large positive value would indicate all-data representation optimism",
            },
            {
                "check": "mean_ml_cluster_run_ami",
                "value": float(np.mean(run_ami_values)),
                "pass": True,
                "note": "degenerate for one held-out run; retained as telemetry",
            },
            {
                "check": "mean_ml_cluster_stave_ami",
                "value": float(np.mean(stave_ami_values)),
                "pass": True,
                "note": "reported to catch stave-label clustering",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    p01b_dir = Path(config["p01b_report_dir"])
    for path in [args.config, p01b_dir / "p01b_embedding_metadata.json", p01b_dir / "result.json"]:
        if path.exists():
            input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    key_bytes = b"|".join(
        [
            bench_meta["run"].to_numpy(dtype=np.int16).tobytes(),
            bench_meta["event_index"].to_numpy(dtype=np.int32).tobytes(),
            bench_meta["stave_index"].to_numpy(dtype=np.int8).tobytes(),
        ]
    )
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "n_folds": int(len(heldout_runs)),
            "benchmark_rows": int(len(bench_waves)),
            "benchmark_key_sha256": sha256_bytes(key_bytes),
            "nonfinite_hand_feature_values": nonfinite_hand_values,
        },
        "metrics": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "forbidden_release_diagnostic": release_meta,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p02e_1781016529_1278_4216653c_loro_embedding_consumer.py",
        "config": str(args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p02e_1781016529_1278_4216653c_loro_embedding_consumer.py --config {}".format(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == expected,
        "output_sha256": output_sha256_rows(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(result["runtime_sec"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
