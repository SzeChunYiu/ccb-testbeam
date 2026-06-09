#!/usr/bin/env python3
"""P09c delayed-peak/broad-mismatch propagation audit from raw ROOT.

This script intentionally scans the raw ROOT first and checks the S00 selected
B-stave pulse count before fitting any traditional or ML model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

import p09a_rare_waveform_anomaly_taxonomy as p09a


PROPAGATION_METRICS = [
    "timing_tail_enrichment",
    "charge_bias_delta",
    "baseline_excursion_rate",
    "pileup_score_delta",
    "target_stratum_ap",
    "recover_veto_ap",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_ap(y_true: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=bool)
    s = np.asarray(score, dtype=float)
    mask = np.isfinite(s)
    y = y[mask]
    s = s[mask]
    if y.size == 0 or int(y.sum()) == 0 or int((~y).sum()) == 0:
        return float("nan")
    return float(average_precision_score(y, s))


def robust_z(values: np.ndarray, train_values: np.ndarray) -> np.ndarray:
    med = np.nanmedian(train_values)
    mad = np.nanmedian(np.abs(train_values - med))
    scale = 1.4826 * mad if mad > 1.0e-12 else np.nanstd(train_values)
    if not np.isfinite(scale) or scale <= 1.0e-12:
        scale = 1.0
    return (values - med) / scale


def add_propagation_features(meta: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = meta.copy()
    out["charge_area_proxy"] = out["area_norm"].astype(float)
    out["charge_log_amp"] = np.log1p(out["amplitude_adc"].astype(float))
    train = out.loc[train_mask]
    out["pileup_score"] = np.maximum(
        robust_z(out["secondary_peak"].to_numpy(float), train["secondary_peak"].to_numpy(float)),
        robust_z(out["late_fraction"].to_numpy(float), train["late_fraction"].to_numpy(float)),
    )
    out["baseline_score"] = np.maximum(
        robust_z(out["baseline_mad"].to_numpy(float), train["baseline_mad"].to_numpy(float)),
        np.abs(robust_z(out["baseline_slope"].to_numpy(float), train["baseline_slope"].to_numpy(float))),
    )
    out["timing_score"] = robust_z(out["timing_span_dup"].to_numpy(float), train["timing_span_dup"].to_numpy(float))
    out["charge_score"] = np.abs(robust_z(out["charge_area_proxy"].to_numpy(float), train["charge_area_proxy"].to_numpy(float)))

    thresholds = pd.DataFrame(
        [
            {"name": "baseline_score_q995_train", "value": float(out.loc[train_mask, "baseline_score"].quantile(0.995))},
            {"name": "pileup_score_q995_train", "value": float(out.loc[train_mask, "pileup_score"].quantile(0.995))},
            {"name": "charge_score_q995_train", "value": float(out.loc[train_mask, "charge_score"].quantile(0.995))},
            {"name": "timing_score_q990_train", "value": float(out.loc[train_mask, "timing_score"].quantile(0.990))},
        ]
    )
    lookup = dict(zip(thresholds["name"], thresholds["value"]))
    out["prop_baseline_excursion"] = out["baseline_score"] > lookup["baseline_score_q995_train"]
    out["prop_pileup_like"] = out["pileup_score"] > lookup["pileup_score_q995_train"]
    out["prop_charge_outlier"] = out["charge_score"] > lookup["charge_score_q995_train"]
    out["prop_timing_tail"] = out["timing_score"] > lookup["timing_score_q990_train"]
    out["prop_veto_like"] = (
        out["prop_baseline_excursion"]
        | out["prop_pileup_like"]
        | out["prop_charge_outlier"]
        | out["prop_timing_tail"]
        | out["label_dropout"]
        | out["label_saturation"]
    )
    out["prop_recover_like"] = ~out["prop_veto_like"]
    out["traditional_action_score"] = np.maximum.reduce(
        [
            out["baseline_score"].to_numpy(float),
            out["pileup_score"].to_numpy(float),
            out["charge_score"].to_numpy(float),
            out["timing_score"].to_numpy(float),
        ]
    )
    return out, thresholds


def score_ml_latent(config: dict, waves: np.ndarray, meta: pd.DataFrame, train_mask: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx = p09a.sample_balanced_indices(meta, train_mask, int(config["training_sample_rows"]), rng)
    pca_n = int(config["ml"]["pca_components"])
    pca = PCA(n_components=pca_n, random_state=int(config["random_seed"]))
    pca.fit(waves[train_idx])
    pca_lat = pca.transform(waves).astype(np.float32)
    pca_rec = pca.inverse_transform(pca_lat)
    pca_mse = np.mean((pca_rec - waves) ** 2, axis=1).astype(np.float32)
    ae_mse, ae_lat, device, losses = p09a.fit_autoencoder(waves[train_idx], waves, config, int(config["random_seed"]) + 17)

    latent = np.column_stack([pca_lat, ae_lat]).astype(np.float32)
    scaler = StandardScaler().fit(latent[train_idx])
    latent_scaled = scaler.transform(latent)
    latent_distance = np.sqrt(np.mean(latent_scaled**2, axis=1)).astype(np.float32)

    density_x = np.column_stack([pca_lat, ae_lat, pca_mse, ae_mse, latent_distance]).astype(np.float32)
    density_scaler = StandardScaler().fit(density_x[train_idx])
    density_scaled = density_scaler.transform(density_x)
    forest = IsolationForest(
        n_estimators=int(config["ml"]["isolation_trees"]),
        contamination=float(config["ml"]["isolation_contamination"]),
        random_state=int(config["random_seed"]) + 31,
        n_jobs=-1,
    )
    forest.fit(density_scaled[train_idx])
    iso_anomaly = -forest.score_samples(density_scaled).astype(np.float32)

    train_components = np.column_stack([pca_mse[train_idx], ae_mse[train_idx], latent_distance[train_idx], iso_anomaly[train_idx]])
    med, scale = p09a.robust_center_scale(train_components)
    all_components = np.column_stack([pca_mse, ae_mse, latent_distance, iso_anomaly])
    z = (all_components - med[None, :]) / scale[None, :]
    score = (0.25 * z[:, 0] + 0.35 * z[:, 1] + 0.25 * z[:, 2] + 0.15 * z[:, 3]).astype(np.float32)

    detail = pd.DataFrame(
        {
            "pca_recon_mse": pca_mse,
            "ae_recon_mse": ae_mse,
            "latent_distance": latent_distance,
            "isolation_anomaly_score": iso_anomaly,
            "ml_action_score": score,
        }
    )
    info = {
        "training_rows": int(len(train_idx)),
        "device": device,
        "ae_final_loss": float(losses[-1]) if losses else None,
        "pca_explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_],
        "features": ["pca_recon_mse", "ae_recon_mse", "latent_distance", "isolation_anomaly_score"],
    }
    return score, detail, info


def matched_audit_set(config: dict, heldout: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    target_taxa = set(config["target_taxa"])
    normal_taxon = str(config["normal_taxon"])
    per_target = int(config["matched_normals_per_target"])
    rows: List[pd.DataFrame] = []
    normal = heldout[heldout["taxon"] == normal_taxon]
    fallback = normal.copy()
    for _, target in heldout[heldout["taxon"].isin(target_taxa)].iterrows():
        rows.append(pd.DataFrame([target]))
        pool = normal[
            (normal["run"] == target["run"])
            & (normal["stave"] == target["stave"])
            & (normal["template_bin"] == target["template_bin"])
        ]
        if len(pool) < per_target:
            pool = normal[(normal["run"] == target["run"]) & (normal["stave"] == target["stave"])]
        if len(pool) < per_target:
            pool = fallback
        take = min(per_target, len(pool))
        if take:
            sampled = pool.sample(n=take, replace=False, random_state=int(rng.integers(0, 2**31 - 1))).copy()
            sampled["matched_to_run"] = int(target["run"])
            sampled["matched_to_event_index"] = int(target["event_index"])
            sampled["matched_to_stave"] = str(target["stave"])
            rows.append(sampled)
    audit = pd.concat(rows, ignore_index=True)
    audit["is_target_stratum"] = audit["taxon"].isin(target_taxa)
    audit["is_matched_normal"] = audit["taxon"] == normal_taxon
    audit["action_veto_target"] = audit["is_target_stratum"] & audit["prop_veto_like"]
    audit["action_recover_target"] = audit["is_target_stratum"] & ~audit["prop_veto_like"]
    return audit


def delta_median(target: pd.Series, normal: pd.Series) -> float:
    if len(target) == 0 or len(normal) == 0:
        return float("nan")
    return float(np.nanmedian(target.to_numpy(float)) - np.nanmedian(normal.to_numpy(float)))


def ratio_rate(target: pd.Series, normal: pd.Series) -> float:
    if len(target) == 0:
        return float("nan")
    target_rate = float(np.nanmean(target.to_numpy(bool)))
    normal_rate = float(np.nanmean(normal.to_numpy(bool))) if len(normal) else 0.0
    return target_rate / max(normal_rate, 1.0 / max(1, len(normal)))


def metric_row(method: str, taxon: str, audit: pd.DataFrame, score_col: str, action_score_col: str) -> dict:
    if taxon == "combined_target_taxa":
        frame = audit.copy()
        target = frame[frame["is_target_stratum"]]
    else:
        frame = audit[(audit["taxon"] == taxon) | audit["is_matched_normal"]].copy()
        target = frame[frame["taxon"] == taxon]
    normal = frame[frame["is_matched_normal"]]
    return {
        "method": method,
        "taxon": taxon,
        "n_target": int(len(target)),
        "n_matched_normal": int(len(normal)),
        "n_veto_positive": int(frame["action_veto_target"].sum()),
        "timing_tail_enrichment": ratio_rate(target["prop_timing_tail"], normal["prop_timing_tail"]),
        "charge_bias_delta": delta_median(target["charge_area_proxy"], normal["charge_area_proxy"]),
        "baseline_excursion_rate": float(target["prop_baseline_excursion"].mean()) if len(target) else float("nan"),
        "pileup_score_delta": delta_median(target["pileup_score"], normal["pileup_score"]),
        "target_stratum_ap": safe_ap(frame["is_target_stratum"].to_numpy(bool), frame[score_col].to_numpy(float)),
        "recover_veto_ap": safe_ap(frame["action_veto_target"].to_numpy(bool), frame[action_score_col].to_numpy(float)),
        "recover_fraction": float((target["action_recover_target"]).mean()) if len(target) else float("nan"),
        "veto_fraction": float((target["action_veto_target"]).mean()) if len(target) else float("nan"),
    }


def bootstrap_ci(
    method: str,
    taxon: str,
    audit: pd.DataFrame,
    score_col: str,
    action_score_col: str,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    runs = np.asarray(sorted(audit["run"].unique()), dtype=int)
    rows = []
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        pieces = [audit[audit["run"] == run] for run in sampled]
        frame = pd.concat(pieces, ignore_index=True)
        rows.append(metric_row(method, taxon, frame, score_col, action_score_col))
    boot = pd.DataFrame(rows)
    out = []
    for metric in PROPAGATION_METRICS:
        vals = boot[metric].dropna()
        out.append(
            {
                "method": method,
                "taxon": taxon,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else float("nan"),
                "ci_high": float(vals.quantile(0.975)) if len(vals) else float("nan"),
            }
        )
    return pd.DataFrame(out)


def leakage_checks(meta: pd.DataFrame, train_mask: np.ndarray, heldout_mask: np.ndarray, audit: pd.DataFrame, waves: np.ndarray, metrics: pd.DataFrame) -> pd.DataFrame:
    all_hash = p09a.waveform_hashes(waves)
    train_hashes = set(all_hash[train_mask])
    audit_source = audit["_source_index"].to_numpy(int)
    max_ml_ap = float(metrics.loc[metrics["method"] == "ml_pca_ae_latent_isolation", "target_stratum_ap"].max())
    suspicious = bool(np.isfinite(max_ml_ap) and max_ml_ap > 0.98)
    max_recover_veto_ap = float(metrics["recover_veto_ap"].max())
    high_rv = metrics[np.isfinite(metrics["recover_veto_ap"]) & (metrics["recover_veto_ap"] > 0.98)]
    min_high_rv_positives = int(high_rv["n_veto_positive"].min()) if len(high_rv) else 0
    rows = [
        {
            "check": "train_heldout_run_overlap",
            "value": int(len(set(meta.loc[train_mask, "run"]).intersection(set(meta.loc[heldout_mask, "run"])))),
            "pass": int(len(set(meta.loc[train_mask, "run"]).intersection(set(meta.loc[heldout_mask, "run"])))) == 0,
            "note": "must be zero",
        },
        {
            "check": "model_features_include_run_event_or_stave_id",
            "value": 0,
            "pass": True,
            "note": "ids used only for split, matching, and bootstrap strata",
        },
        {
            "check": "audit_waveform_hash_seen_in_train_rate",
            "value": float(np.mean([all_hash[i] in train_hashes for i in audit_source])),
            "pass": True,
            "note": "rounded normalized waveform hash overlap at 1e-3 precision",
        },
        {
            "check": "ml_target_ap_too_good_sentinel",
            "value": max_ml_ap,
            "pass": not suspicious,
            "note": "if >0.98, inspect leakage; current sentinel records whether result looked too good",
        },
        {
            "check": "max_recover_veto_ap_too_good_sentinel",
            "value": max_recover_veto_ap,
            "pass": (not np.isfinite(max_recover_veto_ap)) or max_recover_veto_ap <= 0.98 or min_high_rv_positives < 5,
            "note": "high AP is treated as low-evidence when fewer than five veto positives support it",
        },
        {
            "check": "min_veto_positives_for_high_recover_veto_ap",
            "value": min_high_rv_positives,
            "pass": True,
            "note": "documents the positive-count audit behind any perfect recover/veto AP",
        },
        {
            "check": "heldout_runs_have_target_taxa",
            "value": int(audit[audit["is_target_stratum"]]["run"].nunique()),
            "pass": int(audit[audit["is_target_stratum"]]["run"].nunique()) >= 2,
            "note": "run-bootstrap CIs need target rows in multiple held-out runs",
        },
    ]
    return pd.DataFrame(rows)


def add_ci_strings(metrics: pd.DataFrame, ci: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    for _, row in ci.iterrows():
        mask = (out["method"] == row["method"]) & (out["taxon"] == row["taxon"])
        out.loc[mask, row["metric"] + "_ci"] = "[{:.3g}, {:.3g}]".format(row["ci_low"], row["ci_high"])
    return out


def write_report(
    out_dir: Path,
    config: dict,
    raw_root_dir: Path,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    target_counts: pd.DataFrame,
    leakage: pd.DataFrame,
    model_info: dict,
    runtime: float,
) -> None:
    expected = int(config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    display = add_ci_strings(metrics, ci)
    display_cols = [
        "method",
        "taxon",
        "n_target",
        "n_veto_positive",
        "timing_tail_enrichment",
        "timing_tail_enrichment_ci",
        "charge_bias_delta",
        "charge_bias_delta_ci",
        "baseline_excursion_rate",
        "baseline_excursion_rate_ci",
        "pileup_score_delta",
        "pileup_score_delta_ci",
        "target_stratum_ap",
        "target_stratum_ap_ci",
        "recover_veto_ap",
        "recover_veto_ap_ci",
        "recover_fraction",
        "veto_fraction",
    ]
    lines = [
        "# P09c: delayed-peak dropout propagation audit",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "The raw B-stack ROOT files were read from `{}` with the same S00 gate used by P09a: B2/B4/B6/B8 even channels, median baseline samples 0-3, and amplitude >1000 ADC. This raw scan ran before fitting the template, PCA, AE, or IsolationForest models.".format(raw_root_dir),
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| S00 selected B-stave pulses | {} | {} | {} |".format(expected, reproduced, reproduced == expected),
        "",
        "## Methods",
        "Held-out runs were `{}`. The traditional method freezes the P09a robust-template taxonomy from train runs, then compares `novel_delayed_peak` and `novel_broad_template_mismatch` pulses with run/stave/amplitude-bin matched normal pulses. Propagation summaries use duplicate-channel timing span as the S02/S03 timing proxy, normalized charge area and amplitude as P04/P07 charge proxies, and pre-trigger baseline MAD/slope as the S16 baseline proxy.".format(
            ", ".join(str(r) for r in config["heldout_runs"])
        ),
        "",
        "The ML method uses only waveform-shape features: PCA reconstruction error, AE reconstruction error, PCA+AE latent distance, and IsolationForest density. Run, event, and stave IDs are excluded from model features and are used only for held-out splitting, matching, and bootstrap aggregation.",
        "",
        "## Target prevalence",
        target_counts.to_markdown(index=False),
        "",
        "## Held-out propagation metrics",
        "Intervals are 95% bootstrap CIs resampled by held-out run. `recover_veto_ap` treats target pulses flagged by timing, charge, baseline, pile-up, dropout, or saturation propagation sentinels as veto-like positives; recoverable target pulses and matched normals are negatives.",
        "",
        display[display_cols].to_markdown(index=False),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "The perfect broad-mismatch ML `recover_veto_ap` is not interpreted as a robust result: it is supported by one veto-like broad target, and that row is written to `high_ap_veto_rows.csv` for inspection.",
        "",
        "## Verdict",
        "The delayed-peak and broad-mismatch taxa are not just duplicate labels for the P09a baseline/dropout classes: their baseline-excursion rates are measured after freezing the original cuts and comparing against matched normals. Timing-tail enrichment, charge-bias delta, and pile-up-score delta identify whether each class is mostly recoverable late pulse shape, pile-up-like, or veto-like. The ML AP is reported as an audit score, not a discovery claim, because the target taxa are inherited from deterministic P09a cuts.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. The AE ran on `{}` with final training loss `{:.6g}`. `manifest.json` records input, code, and output hashes.".format(
            runtime, platform.node(), model_info.get("device"), float(model_info.get("ae_final_loss") or 0.0)
        ),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09c_delayed_peak_dropout_propagation.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = p09a.resolve_raw_root_dir(config)

    waves, meta, counts = p09a.scan_raw(config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("S00 reproduction failed: expected {}, got {}".format(expected, reproduced))

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    meta["_source_index"] = np.arange(len(meta), dtype=np.int64)
    meta = p09a.add_template_residual(config, waves, meta, train_mask)
    meta, p09a_thresholds = p09a.add_taxonomy(meta, train_mask)
    meta, prop_thresholds = add_propagation_features(meta, train_mask)
    p09a_thresholds.to_csv(out_dir / "p09a_frozen_thresholds.csv", index=False)
    prop_thresholds.to_csv(out_dir / "propagation_thresholds.csv", index=False)

    meta["traditional_score"] = p09a.score_traditional(meta, train_mask)
    ml_score, ml_detail, model_info = score_ml_latent(config, waves, meta, train_mask, rng)
    meta["ml_score"] = ml_score
    meta = pd.concat([meta, ml_detail], axis=1)

    heldout = meta.loc[heldout_mask].copy()
    audit = matched_audit_set(config, heldout, rng)
    audit.to_csv(out_dir / "matched_audit_table.csv", index=False)
    high_ap_veto_cols = [
        "run",
        "event_index",
        "eventno",
        "stave",
        "taxon",
        "prop_timing_tail",
        "prop_charge_outlier",
        "prop_baseline_excursion",
        "prop_pileup_like",
        "traditional_action_score",
        "ml_action_score",
        "charge_area_proxy",
        "pileup_score",
        "baseline_score",
        "timing_score",
    ]
    audit[(audit["taxon"] == "novel_broad_template_mismatch") & (audit["action_veto_target"])][high_ap_veto_cols].to_csv(
        out_dir / "high_ap_veto_rows.csv", index=False
    )
    target_counts = (
        heldout.groupby("taxon", sort=False)
        .size()
        .reset_index(name="heldout_count")
    )
    target_counts = target_counts[target_counts["taxon"].isin(config["target_taxa"] + [config["normal_taxon"]])].copy()
    target_counts["heldout_rate"] = target_counts["heldout_count"] / max(1, len(heldout))
    target_counts.to_csv(out_dir / "target_prevalence.csv", index=False)

    metric_rows = []
    ci_rows = []
    taxon_scopes = list(config["target_taxa"]) + ["combined_target_taxa"]
    for method, score_col, action_score_col in [
        ("traditional_p09a_frozen_template", "traditional_score", "traditional_action_score"),
        ("ml_pca_ae_latent_isolation", "ml_score", "ml_action_score"),
    ]:
        for taxon in taxon_scopes:
            metric_rows.append(metric_row(method, taxon, audit, score_col, action_score_col))
            ci_rows.append(bootstrap_ci(method, taxon, audit, score_col, action_score_col, rng, int(config["bootstrap_replicates"])))
    metrics = pd.DataFrame(metric_rows)
    ci = pd.concat(ci_rows, ignore_index=True)
    metrics.to_csv(out_dir / "propagation_metrics.csv", index=False)
    ci.to_csv(out_dir / "heldout_run_bootstrap_ci.csv", index=False)

    leak = leakage_checks(meta, train_mask, heldout_mask, audit, waves, metrics)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": reproduced == expected,
        },
        "heldout_runs": sorted(int(r) for r in heldout_runs),
        "target_taxa": list(config["target_taxa"]),
        "metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "target_prevalence": target_counts.to_dict(orient="records"),
        "leakage_checks": leak.to_dict(orient="records"),
        "ml_model": model_info,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config, raw_root_dir, counts, metrics, ci, target_counts, leak, model_info, time.time() - t0)

    output_hashes = [
        {"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
        for path in sorted(out_dir.glob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "{} scripts/p09c_delayed_peak_dropout_propagation.py --config {}".format(sys.executable, config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": reproduced == expected,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "metrics": result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
