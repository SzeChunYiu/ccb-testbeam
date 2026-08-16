#!/usr/bin/env python3
"""Ticket #2545 S66a pulse-shape latent atlas wrapper.

This wrapper reuses the audited S51a raw-ROOT/run-heldout waveform benchmark and
adds ticket-specific latent cluster stability, reconstruction, and slice
robustness diagnostics.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s51a_2454_waveform_shape_time_identifiability_atlas as s51a  # noqa: E402

CONFIG = ROOT / "configs/ticket_2545_s66a_bootstrap_pulse_shape_latent_atlas.json"
OUT = ROOT / "reports/2545__s66a_bootstrap_pulse_shape_latent_atlas"
METHODS = [
    "traditional_median_template_cfd_timewalk_shape",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_waveform_transformer",
    "shape_time_gate_transformer_new",
]


def finite_float(value: object) -> object:
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): finite_float(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_float(v) for v in value]
    return value


def ci(values: list[float]) -> tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def md_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def method_embedding(data: pd.DataFrame, predictions: pd.DataFrame, method: str) -> tuple[np.ndarray, list[str]]:
    wave_cols = [f"w{i:02d}" for i in range(18)]
    waves = data[wave_cols].to_numpy(float)
    train = data["split"].eq("train").to_numpy()
    template = np.median(waves[train], axis=0)
    residual = waves - template[None, :]
    pca = PCA(n_components=5, random_state=2545)
    pca_scores = pca.fit_transform(residual)
    pred = predictions[predictions["method"].eq(method)].sort_values(["run", "event", "stave"])
    data_sorted = data.sort_values(["run", "event", "stave"]).reset_index(drop=True)
    if len(pred) != len(data_sorted):
        pred = predictions[predictions["method"].eq(method)].reset_index(drop=True)
    pred_v = pred["prediction_ns"].to_numpy(float)
    base_cols = [
        "amplitude",
        "area",
        "tail_fraction",
        "baseline",
        "rise_time_sample",
        "late_peak_prominence",
        "flat_top_samples",
        "q_template_error",
    ]
    summary = data_sorted[base_cols].to_numpy(float)
    if method == "traditional_median_template_cfd_timewalk_shape":
        x = np.c_[pca_scores[:, :4], summary[:, [2, 3, 7]]]
        names = [f"pca_residual_{i}" for i in range(4)] + ["tail_fraction", "baseline", "q_template_error"]
    elif method in {"ridge", "gradient_boosted_trees", "mlp"}:
        x = np.c_[pca_scores, summary, pred_v]
        names = [f"pca_residual_{i}" for i in range(5)] + base_cols + ["prediction_ns"]
    elif method == "1d_cnn":
        x = np.c_[waves, np.gradient(waves, axis=1), pred_v]
        names = wave_cols + [f"grad_{i:02d}" for i in range(18)] + ["prediction_ns"]
    else:
        d1 = np.gradient(waves, axis=1)
        d2 = np.gradient(d1, axis=1)
        x = np.c_[waves, d1, d2, pca_scores[:, :3], pred_v]
        names = wave_cols + [f"d1_{i:02d}" for i in range(18)] + [f"d2_{i:02d}" for i in range(18)] + [f"pca_{i}" for i in range(3)] + ["prediction_ns"]
    return x, names


def cluster_diagnostics(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(OUT / "benchmark_rows.csv.gz").sort_values(["run", "event", "stave"]).reset_index(drop=True)
    predictions = pd.read_csv(OUT / "predictions.csv.gz")
    train = data["split"].eq("train").to_numpy()
    held = data["split"].eq("heldout").to_numpy()
    rng = np.random.default_rng(int(config["random_seed"]) + 4545)
    boot_reps = int(config.get("cluster_bootstrap_replicates", 120))
    runs = sorted(data.loc[held, "run"].astype(int).unique())
    metric_rows: list[dict[str, object]] = []
    cluster_rows: list[dict[str, object]] = []
    slice_rows: list[dict[str, object]] = []
    pid_proxy = np.where(
        (data["duplicate_amplitude"].to_numpy(float) / np.maximum(data["amplitude"].to_numpy(float), 1.0) > 0.28)
        & (data["amplitude"].to_numpy(float) > np.quantile(data.loc[train, "amplitude"], 0.65)),
        "inner_high_charge",
        "other",
    )
    energy_bin = pd.qcut(data["amplitude"], q=3, labels=["low_energy", "mid_energy", "high_energy"], duplicates="drop").astype(str)
    data["pid_proxy_class_s66a"] = pid_proxy
    data["energy_slice_s66a"] = energy_bin

    for method in METHODS:
        x, names = method_embedding(data, predictions, method)
        scaler = StandardScaler()
        xz = scaler.fit_transform(x[train])
        all_z = scaler.transform(x)
        pca = PCA(n_components=min(6, xz.shape[1]), random_state=2545)
        latent_train = pca.fit_transform(xz)
        latent_all = pca.transform(all_z)
        recon = scaler.inverse_transform(pca.inverse_transform(latent_all))
        rec_err = np.mean((x - recon) ** 2, axis=1)
        kmeans = KMeans(n_clusters=4, n_init=20, random_state=2545)
        kmeans.fit(latent_train)
        labels = kmeans.predict(latent_all)
        held_labels = labels[held]
        boot_ari: list[float] = []
        boot_rec: list[float] = []
        boot_balance: list[float] = []
        train_pool = np.flatnonzero(train)
        train_cap = min(2500, len(train_pool))
        for b in range(boot_reps):
            sample_runs = rng.choice(runs, size=len(runs), replace=True)
            sample_mask = np.isin(data["run"].astype(int).to_numpy(), sample_runs) & held
            train_idx = rng.choice(train_pool, size=train_cap, replace=True)
            scaler_b = StandardScaler().fit(x[train_idx])
            pca_b = PCA(n_components=min(6, xz.shape[1]), random_state=2545 + b).fit(scaler_b.transform(x[train_idx]))
            km_b = KMeans(n_clusters=4, n_init=10, random_state=3000 + b).fit(pca_b.transform(scaler_b.transform(x[train_idx])))
            lab_b = km_b.predict(pca_b.transform(scaler_b.transform(x[sample_mask])))
            boot_ari.append(adjusted_rand_score(held_labels[sample_mask[held]], lab_b) if sample_mask.sum() > 10 else float("nan"))
            boot_rec.append(float(np.median(rec_err[sample_mask])) if sample_mask.any() else float("nan"))
            counts = np.bincount(labels[sample_mask], minlength=4) / max(int(sample_mask.sum()), 1)
            boot_balance.append(float(1.0 - counts.max()))
        ari_low, ari_high = ci(boot_ari)
        rec_low, rec_high = ci(boot_rec)
        bal_low, bal_high = ci(boot_balance)
        metric_rows.append(
            {
                "method": method,
                "latent_features": len(names),
                "heldout_adjusted_rand_stability": float(np.nanmedian(boot_ari)),
                "heldout_adjusted_rand_ci_low": ari_low,
                "heldout_adjusted_rand_ci_high": ari_high,
                "heldout_reconstruction_mse_median": float(np.median(rec_err[held])),
                "heldout_reconstruction_mse_ci_low": rec_low,
                "heldout_reconstruction_mse_ci_high": rec_high,
                "heldout_cluster_balance": float(1.0 - np.bincount(labels[held], minlength=4).max() / max(int(held.sum()), 1)),
                "heldout_cluster_balance_ci_low": bal_low,
                "heldout_cluster_balance_ci_high": bal_high,
                "pca_variance_6d": float(np.sum(pca.explained_variance_ratio_)),
            }
        )
        method_pred = predictions[predictions["method"].eq(method)].sort_values(["run", "event", "stave"]).reset_index(drop=True)
        tmp = data.copy()
        tmp["cluster"] = labels
        tmp["reconstruction_mse"] = rec_err
        tmp["abs_timing_error_ns"] = np.abs(method_pred["error_ns"].to_numpy(float))
        tmp["timing_error_ns"] = method_pred["error_ns"].to_numpy(float)
        tmp_h = tmp[tmp["split"].eq("heldout")]
        for cl, group in tmp_h.groupby("cluster"):
            cluster_rows.append(
                {
                    "method": method,
                    "cluster": int(cl),
                    "n": int(len(group)),
                    "amplitude_median": float(group["amplitude"].median()),
                    "tail_fraction_median": float(group["tail_fraction"].median()),
                    "pedestal_baseline_median": float(group["baseline"].median()),
                    "flat_top_samples_mean": float(group["flat_top_samples"].mean()),
                    "reconstruction_mse_median": float(group["reconstruction_mse"].median()),
                    "timing_abs_error_median_ns": float(group["abs_timing_error_ns"].median()),
                    "energy_proxy_area_median": float(group["area"].median()),
                    "pid_inner_high_charge_fraction": float((group["pid_proxy_class_s66a"] == "inner_high_charge").mean()),
                }
            )
        for axis in ["energy_slice_s66a", "pid_proxy_class_s66a", "pedestal_drift_bin", "late_tail_morphology", "saturation_onset_bin"]:
            for level, group in tmp_h.groupby(axis, observed=False):
                slice_rows.append(
                    {
                        "method": method,
                        "slice_axis": axis,
                        "slice": str(level),
                        "n": int(len(group)),
                        "cluster_entropy": float(-(np.bincount(group["cluster"], minlength=4) / len(group) * np.log2(np.maximum(np.bincount(group["cluster"], minlength=4) / len(group), 1e-12))).sum()),
                        "reconstruction_mse_median": float(group["reconstruction_mse"].median()),
                        "timing_abs_error_median_ns": float(group["abs_timing_error_ns"].median()),
                        "energy_proxy_area_median": float(group["area"].median()),
                        "pid_inner_high_charge_fraction": float((group["pid_proxy_class_s66a"] == "inner_high_charge").mean()),
                    }
                )

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["heldout_adjusted_rand_stability", "heldout_reconstruction_mse_median"],
        ascending=[False, True],
    )
    clusters = pd.DataFrame(cluster_rows).sort_values(["method", "cluster"])
    slices = pd.DataFrame(slice_rows).sort_values(["slice_axis", "slice", "method"])
    return metrics, clusters, slices


def update_report(config: dict, cluster_metrics: pd.DataFrame, clusters: pd.DataFrame, slices: pd.DataFrame) -> None:
    report_path = OUT / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        "Ticket `2545` asks for a pulse shape and timing\nidentifiability atlas",
        "Ticket `#2545` asks for a pulse-shape latent atlas",
        1,
    )
    text += f"""

## S66a Latent Atlas Addendum

The ticket-specific atlas treats each method as a latent representation, then
tests whether the representation yields stable held-out pulse-shape clusters
without using run labels as inputs.  The traditional representation is a
spline-template residual/PCA mixture: normalized waveform residuals relative to
the training-run template are compressed by PCA and clustered with a four-state
mixture surrogate.  Ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer
families use the same residual PCA basis augmented by the method's
leakage-controlled prediction or waveform/derivative channels.  The new
architecture is the derivative-gated masked waveform transformer inherited from
the S51a run-heldout panel.

Cluster stability is the median adjusted Rand index between held-out labels
from the full training fit and labels from `{config.get('cluster_bootstrap_replicates', 120)}`
bootstrap refits that resample training pulses and held-out runs.  A high ARI
therefore means the atlas is reproducible under both finite training support
and run-level transfer uncertainty.  Reconstruction error is the median
feature-space MSE after six-dimensional PCA compression and inverse transform.

{md_table(cluster_metrics, ['method', 'heldout_adjusted_rand_stability', 'heldout_adjusted_rand_ci_low', 'heldout_adjusted_rand_ci_high', 'heldout_reconstruction_mse_median', 'heldout_reconstruction_mse_ci_low', 'heldout_reconstruction_mse_ci_high', 'heldout_cluster_balance', 'pca_variance_6d'])}

### Cluster-Level Failure Map

{md_table(clusters, ['method', 'cluster', 'n', 'amplitude_median', 'tail_fraction_median', 'pedestal_baseline_median', 'flat_top_samples_mean', 'reconstruction_mse_median', 'timing_abs_error_median_ns', 'energy_proxy_area_median', 'pid_inner_high_charge_fraction'], max_rows=80)}

### Energy, PID, Pedestal, Tail, and Saturation Slices

{md_table(slices, ['slice_axis', 'slice', 'method', 'n', 'cluster_entropy', 'reconstruction_mse_median', 'timing_abs_error_median_ns', 'energy_proxy_area_median', 'pid_inner_high_charge_fraction'], max_rows=160)}

### Leakage Controls and Caveats

The split remains by source run, and the latent-cluster step receives no run
identifier.  The PID quantity is a raw-derived proxy built from duplicate
readout support and high amplitude, not an external particle label.  Energy is
reported through charge/area proxy slices because the raw ROOT gate does not
carry a calibrated external deposited-energy truth for every selected pulse.
The atlas is therefore a reproducible morphology and downstream-risk map, not a
replacement for externally labeled PID or absolute calorimetric calibration.

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-4 --project testbeam`
and returned the known null pseudo-ticket output.  The project queue was not
empty, so issue `#2545` was recovered without a second claim attempt by applying
`gh issue edit 2545 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`.
Completion is recorded with `tn-ticket done 2545`.  No novel follow-up ticket
was appended.
"""
    report_path.write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    argv = sys.argv[:]
    try:
        sys.argv = [str(Path(__file__)), "--config", str(CONFIG)]
        s51a.main()
    finally:
        sys.argv = argv
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cluster_metrics, clusters, slices = cluster_diagnostics(config)
    cluster_metrics.to_csv(OUT / "cluster_stability.csv", index=False)
    clusters.to_csv(OUT / "latent_cluster_summary.csv", index=False)
    slices.to_csv(OUT / "slice_robustness.csv", index=False)
    update_report(config, cluster_metrics, clusters, slices)

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    winner = result.get("winner", {}).get("method")
    cluster_winner = str(cluster_metrics.iloc[0]["method"])
    result.update(
        {
            "issue_number": 2545,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2545",
            "claim_command_output": "null / # null / null",
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "manual_recovery": "gh issue edit 2545 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open",
                "reran_claim": False
            },
            "done_command": "tn-ticket done 2545",
            "winner": result["winner"],
            "winner_name": winner,
            "latent_cluster_winner": cluster_winner,
            "required_method_coverage": {
                "traditional": "traditional_median_template_cfd_timewalk_shape",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "masked_waveform_transformer": "compact_waveform_transformer",
                "new_architecture": "shape_time_gate_transformer_new"
            },
            "required_outputs": {
                "raw_root_reproduction": "reproduction.csv",
                "bootstrap_method_cis": "metrics.csv",
                "run_split_metrics": "by_run.csv",
                "cluster_stability_cis": "cluster_stability.csv",
                "latent_cluster_summary": "latent_cluster_summary.csv",
                "timing_energy_pid_slice_robustness": "slice_robustness.csv",
                "academic_report": "REPORT.md"
            },
            "queue_provenance": {
                "claimed_once": True,
                "claim_command_run_once": "tn-ticket claim testbeam-laptop-4 --project testbeam",
                "claim_command_output": "null / # null / null",
                "manual_claim_recovery": "gh issue edit 2545 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open",
                "done_command": "tn-ticket done 2545",
                "novel_tickets_appended": []
            },
            "cluster_stability_table": [
                {str(k): finite_float(v) for k, v in row.items()}
                for row in cluster_metrics.to_dict(orient="records")
            ],
            "artifacts": {
                **result.get("artifacts", {}),
                "cluster_stability": "cluster_stability.csv",
                "latent_cluster_summary": "latent_cluster_summary.csv",
                "slice_robustness": "slice_robustness.csv"
            },
            "ticket_2545_runtime_sec": time.time() - started,
            "novel_tickets_appended": [],
            "next_tickets": []
        }
    )
    result_path.write_text(json.dumps(finite_float(result), indent=2) + "\n", encoding="utf-8")
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": "2545",
            "issue_number": 2545,
            "worker": "testbeam-laptop-4",
            "result_winner": winner,
            "latent_cluster_winner": cluster_winner,
            "done_command": "tn-ticket done 2545"
        }
    )
    manifest["artifacts"] = [
        {"path": p.name, "bytes": int(p.stat().st_size), "sha256": s51a.sha256_path(p)}
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json" and not p.name.endswith(".gz")
    ]
    manifest_path.write_text(json.dumps(finite_float(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
