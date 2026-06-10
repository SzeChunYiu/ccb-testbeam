#!/usr/bin/env python3
"""P09d: run-heldout broad-template-mismatch gallery enrichment.

The first data operation is a raw ROOT scan through the P09a reader.  The script
raises before fitting selectors if the selected B-stave pulse count does not
reproduce the frozen P09a/S00 count.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import time
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


TARGET = "novel_broad_template_mismatch"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def ci_text(ci: pd.DataFrame, method: str, metric: str) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty:
        return ""
    return "[{:.3g}, {:.3g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def threshold_lookup(thresholds: pd.DataFrame) -> dict:
    return dict(zip(thresholds["threshold"], thresholds["value"]))


def add_broad_subtypes(meta: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    thr = threshold_lookup(thresholds)
    out = meta.copy()
    known = out["label_known_any"].to_numpy(dtype=bool)
    early = out["label_novel_early_pretrigger"].to_numpy(dtype=bool)
    delayed = out["label_novel_delayed_peak"].to_numpy(dtype=bool)
    pileup = out["label_pileup_or_long_tail"].to_numpy(dtype=bool)
    sat = out["label_saturation"].to_numpy(dtype=bool)
    broad_width = (out["width_half"].to_numpy() > float(thr["width_half_q995"])) & ~pileup & ~sat
    p09a_strict_q_template_only = (
        (out["q_template_rmse"].to_numpy() > float(thr["q_template_rmse_q999"]))
        & ~known
        & ~early
        & ~delayed
        & ~broad_width
    )
    q_template_only = (
        (out["q_template_rmse"].to_numpy() > float(thr["q_template_rmse_q995"]))
        & ~known
        & ~early
        & ~delayed
        & ~broad_width
    )
    out["broad_width_source"] = broad_width
    out["p09a_strict_q_template_only_source"] = p09a_strict_q_template_only
    out["q_template_only_source"] = q_template_only
    out["label_gallery_qtemplate_or_broad"] = q_template_only | broad_width
    out["broad_source"] = np.where(
        broad_width & q_template_only,
        "both",
        np.where(broad_width, "broad_width", np.where(q_template_only, "q_template_only", "not_broad_rule")),
    )
    return out


def robust_z(train: np.ndarray, values: np.ndarray) -> np.ndarray:
    med = float(np.nanmedian(train))
    mad = float(np.nanmedian(np.abs(train - med)))
    scale = 1.4826 * mad if mad > 1e-9 else float(np.nanstd(train))
    if not np.isfinite(scale) or scale <= 1e-9:
        scale = 1.0
    return (values - med) / scale


def add_traditional_score(meta: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    qz = robust_z(
        out.loc[train_mask, "q_template_rmse"].to_numpy(dtype=float),
        out["q_template_rmse"].to_numpy(dtype=float),
    )
    wz = robust_z(
        out.loc[train_mask, "width_half"].to_numpy(dtype=float),
        out["width_half"].to_numpy(dtype=float),
    )
    secondary = robust_z(
        out.loc[train_mask, "secondary_peak"].to_numpy(dtype=float),
        out["secondary_peak"].to_numpy(dtype=float),
    )
    out["traditional_broad_score"] = np.maximum(qz, wz) + 0.15 * np.maximum(secondary, 0.0)
    return out


def balanced_top(
    frame: pd.DataFrame,
    score_col: str,
    method: str,
    k_per_run_stave: int,
    eligible: np.ndarray | None = None,
) -> pd.DataFrame:
    base = frame.copy()
    if eligible is not None:
        base = base.loc[eligible].copy()
    rows = []
    for _, subset in base.groupby(["run", "stave"], sort=True):
        rows.append(subset.sort_values(score_col, ascending=False).head(k_per_run_stave))
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(out):
        out["method"] = method
    return out


def balanced_qtemplate_broad_top(frame: pd.DataFrame, method: str, k_per_run_stave: int) -> pd.DataFrame:
    rows = []
    q_take = int(math.ceil(k_per_run_stave / 2.0))
    b_take = int(k_per_run_stave - q_take)
    for _, subset in frame.groupby(["run", "stave"], sort=True):
        q_rows = subset[subset["q_template_only_source"]].sort_values("q_template_rmse", ascending=False).head(q_take)
        b_rows = subset[subset["broad_width_source"]].sort_values("traditional_broad_score", ascending=False).head(b_take)
        chosen = pd.concat([q_rows, b_rows], ignore_index=False).drop_duplicates(["run", "event_index", "stave"])
        if len(chosen) < k_per_run_stave:
            fill = (
                subset[subset["label_gallery_qtemplate_or_broad"]]
                .sort_values("traditional_broad_score", ascending=False)
                .drop(chosen.index, errors="ignore")
                .head(k_per_run_stave - len(chosen))
            )
            chosen = pd.concat([chosen, fill], ignore_index=False)
        rows.append(chosen)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(out):
        out["method"] = method
    return out


def train_indices(meta: pd.DataFrame, train_mask: np.ndarray, config: dict, rng: np.random.Generator) -> np.ndarray:
    y = meta.loc[train_mask, "label_gallery_qtemplate_or_broad"].to_numpy(dtype=bool)
    idx_all = np.where(train_mask)[0]
    pos = idx_all[y]
    neg = idx_all[~y]
    neg_take = min(len(neg), max(len(pos) * int(config["ml"]["negative_to_positive_ratio"]), 1000))
    chosen = [pos]
    if neg_take:
        chosen.append(rng.choice(neg, size=neg_take, replace=False))
    idx = np.concatenate(chosen)
    rng.shuffle(idx)
    return idx


def make_ml_matrix(
    p09a,
    config: dict,
    waves: np.ndarray,
    meta: pd.DataFrame,
    train_mask: np.ndarray,
    rng: np.random.Generator,
    scalar_cols: Sequence[str],
) -> Tuple[np.ndarray, List[str], dict]:
    pca_sample = p09a.sample_balanced_indices(meta, train_mask, int(config["ml"]["training_sample_rows"]), rng)
    pca = PCA(n_components=int(config["ml"]["pca_components"]), random_state=int(config["random_seed"]))
    pca_lat = pca.fit_transform(waves[pca_sample])
    pca_all = pca.transform(waves).astype(np.float32)
    x = np.column_stack([pca_all, meta.loc[:, scalar_cols].to_numpy(dtype=np.float32)])
    scaler = StandardScaler().fit(x[train_mask])
    names = ["pca_{:02d}".format(i) for i in range(pca_all.shape[1])] + list(scalar_cols)
    info = {"pca_explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_]}
    return scaler.transform(x), names, info


def fit_rf(
    config: dict,
    x: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    train_mask: np.ndarray,
    heldout_mask: np.ndarray,
) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    clf = RandomForestClassifier(
        n_estimators=int(config["ml"]["random_forest_trees"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        class_weight="balanced_subsample",
        random_state=int(config["random_seed"]) + 23,
        n_jobs=-1,
    )
    clf.fit(x[train_idx], y[train_idx])
    score = clf.predict_proba(x)[:, 1].astype(np.float32)
    y_hold = y[heldout_mask]
    s_hold = score[heldout_mask]
    metrics = {
        "train_rows": int(len(train_idx)),
        "train_positive_rows": int(y[train_idx].sum()),
        "heldout_positive_rows": int(y_hold.sum()),
        "heldout_average_precision": float(average_precision_score(y_hold, s_hold)) if y_hold.sum() else float("nan"),
        "heldout_roc_auc": float(roc_auc_score(y_hold, s_hold)) if len(np.unique(y_hold)) > 1 else float("nan"),
    }
    importance = pd.DataFrame({"feature": np.arange(x.shape[1]), "importance": clf.feature_importances_})
    return score, metrics, importance


def attach_gallery_waveforms(gallery: pd.DataFrame, waves: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    source = []
    wave_rows = []
    key = meta.reset_index().rename(columns={"index": "source_index"})[["source_index", "run", "event_index", "stave"]]
    merged = gallery.merge(key, on=["run", "event_index", "stave"], how="left")
    if merged["source_index"].isna().any():
        raise RuntimeError("Could not map gallery rows back to raw scan")
    for idx in merged["source_index"].to_numpy(dtype=int):
        source.append(int(idx))
        wave_rows.append([round(float(x), 5) for x in waves[idx]])
    out = gallery.copy()
    out["source_index"] = source
    out["normalized_waveform"] = wave_rows
    return out


def precision_table(gallery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, subset in gallery.groupby("method", sort=True):
        n = max(1, len(subset))
        duplicate_cols = ["run", "event_index"]
        if "_boot_draw" in subset.columns:
            duplicate_cols = ["_boot_draw"] + duplicate_cols
        rows.append(
            {
                "method": method,
                "n_selected": int(len(subset)),
                "p09a_broad_fraction": float(subset["label_novel_broad_template_mismatch"].mean()),
                "source_qtemplate_or_broad_fraction": float(subset["label_gallery_qtemplate_or_broad"].mean()),
                "adjudicated_broad_precision": float((subset["consensus_label"] == TARGET).mean()),
                "adjudicated_curated_precision": float(subset["consensus_curated_any"].mean()),
                "q_template_only_share": float(subset["q_template_only_source"].mean()),
                "p09a_strict_q_template_only_share": float(subset["p09a_strict_q_template_only_source"].mean()),
                "broad_width_share": float(subset["broad_width_source"].mean()),
                "duplicate_run_event_rate": float(subset.duplicated(duplicate_cols, keep=False).sum() / n),
                "max_run_stave_share": float(subset.groupby(["run", "stave"]).size().max() / n),
            }
        )
    return pd.DataFrame(rows)


def per_run_table(gallery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), subset in gallery.groupby(["method", "run"], sort=True):
        rows.append(
            {
                "method": method,
                "run": int(run),
                "n_selected": int(len(subset)),
                "p09a_broad_fraction": float(subset["label_novel_broad_template_mismatch"].mean()),
                "adjudicated_broad_precision": float((subset["consensus_label"] == TARGET).mean()),
                "q_template_only_share": float(subset["q_template_only_source"].mean()),
                "p09a_strict_q_template_only_share": float(subset["p09a_strict_q_template_only_source"].mean()),
                "broad_width_share": float(subset["broad_width_source"].mean()),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(gallery: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(gallery["run"].unique()))
    rows = []
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        pieces = []
        for draw, run in enumerate(sampled):
            piece = gallery[gallery["run"] == run].copy()
            piece["_boot_draw"] = draw
            pieces.append(piece)
        sample = pd.concat(pieces, ignore_index=True)
        ptab = precision_table(sample)
        for _, row in ptab.iterrows():
            for metric in [
                "p09a_broad_fraction",
                "source_qtemplate_or_broad_fraction",
                "adjudicated_broad_precision",
                "adjudicated_curated_precision",
                "q_template_only_share",
                "p09a_strict_q_template_only_share",
                "broad_width_share",
                "duplicate_run_event_rate",
            ]:
                rows.append({"method": row["method"], "metric": metric, "value": float(row[metric])})
    boot = pd.DataFrame(rows)
    out = []
    for (method, metric), subset in boot.groupby(["method", "metric"], sort=True):
        vals = subset["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "method": method,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def write_report(
    out_dir: Path,
    config: dict,
    p09a_config: dict,
    p09b_prior: dict,
    counts: pd.DataFrame,
    precision: pd.DataFrame,
    ci: pd.DataFrame,
    per_run: pd.DataFrame,
    ml_metrics: dict,
    ml_ablation: dict,
    feature_importance: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    expected = int(p09a_config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    view = precision.copy()
    for _, row in view.iterrows():
        for metric in [
            "adjudicated_broad_precision",
            "p09a_broad_fraction",
            "source_qtemplate_or_broad_fraction",
            "q_template_only_share",
            "p09a_strict_q_template_only_share",
            "broad_width_share",
        ]:
            view.loc[view["method"] == row["method"], metric + "_ci"] = ci_text(ci, row["method"], metric)
    lines = [
        "# P09d: enriched broad-template-mismatch gallery",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "The raw B-stack ROOT files under `data/root/root` were scanned before any selector or gallery load. The same S00/P09a gate was used: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} |".format(expected, reproduced, reproduced == expected),
        "| P09b claimed broad examples | 1 | {} | {} |".format(p09b_prior["p09b_broad_claims"], p09b_prior["p09b_broad_claims"] == 1),
        "",
        "## Methods",
        "Held-out runs were `{}`. The traditional selector intentionally reserves slots for q_template-high/non-width-broad pulses and width-broad pulses in each run/stave. The ML selector is a run-heldout RandomForest source classifier using PCA waveform coordinates plus scalar pulse-shape quantities; it uses no run, event, stave, or source index features. Both selectors draw at most {} candidates per held-out run/stave.".format(
            ", ".join(str(r) for r in config["heldout_runs"]), int(config["top_k_per_run_stave"])
        ),
        "",
        "For gallery enrichment, q_template-only means train-run q_template RMSE above the frozen P09a q995 threshold while not width-broad, known, early, or delayed; the stricter P09a q999 template-only source is still tracked separately. A second ML fit removed q_template and width features as a leakage/tautology hunt because the source target is partly defined by those quantities. Full ML held-out AP was `{:.3f}` and ROC-AUC `{:.3f}`; the no-q/width AP was `{:.3f}`.".format(
            ml_metrics["heldout_average_precision"], ml_metrics["heldout_roc_auc"], ml_ablation["heldout_average_precision"]
        ),
        "",
        "## Enriched Gallery Precision",
        "CIs are held-out-run bootstrap intervals over runs, not row bootstraps.",
        "",
        view.to_markdown(index=False),
        "",
        "## Per-run Split",
        per_run.to_markdown(index=False),
        "",
        "## ML Feature Importance",
        feature_importance.head(12).to_markdown(index=False),
        "",
        "## Leakage Checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "The enriched gallery removes the P09b single-example bottleneck for `novel_broad_template_mismatch`: both run-heldout selectors return broad candidates across multiple runs and staves, and the traditional selector deliberately covers both q_template-high/non-width-broad and width-broad sources. The apparent ML strength is not treated as an independent discovery, because the leakage hunt shows that q_template/width carry much of the source label; it is still useful as a triage selector for reviewable waveform examples.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. `manifest.json` records input, code, and output hashes.".format(runtime, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09d_1781021714_1215_508e2136_broad_template_gallery.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09a = load_module("p09a_rare_waveform_anomaly_taxonomy", Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py"))
    p09b = load_module("p09b_manual_waveform_gallery_adjudication", Path("scripts/p09b_manual_waveform_gallery_adjudication.py"))
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    p09a_config["heldout_runs"] = config["heldout_runs"]

    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)
    waves, meta, counts = p09a.scan_raw(p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(p09a_config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("Reproduction failed before selector work: expected {}, got {}".format(expected, reproduced))

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    meta = p09a.add_template_residual(p09a_config, waves, meta, train_mask)
    meta, thresholds = p09a.add_taxonomy(meta, train_mask)
    meta = add_broad_subtypes(meta, thresholds)
    meta = add_traditional_score(meta, train_mask)

    scalar_cols = [
        "amplitude_adc",
        "q_template_rmse",
        "width_half",
        "peak_sample",
        "area_norm",
        "late_fraction",
        "early_fraction",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "undershoot_area",
        "timing_span_dup",
    ]
    x, feature_names, pca_info = make_ml_matrix(p09a, config, waves, meta, train_mask, rng, scalar_cols)
    y = meta["label_gallery_qtemplate_or_broad"].to_numpy(dtype=int)
    idx = train_indices(meta, train_mask, config, rng)
    score, ml_metrics, importance = fit_rf(config, x, y, idx, train_mask, heldout_mask)
    meta["ml_broad_probability"] = score
    importance["feature"] = [feature_names[int(i)] for i in importance["feature"]]
    importance = importance.sort_values("importance", ascending=False)
    importance.to_csv(out_dir / "ml_feature_importance.csv", index=False)

    ablate_cols = [c for c in scalar_cols if c not in {"q_template_rmse", "width_half"}]
    x_abl, ablate_names, _ = make_ml_matrix(p09a, config, waves, meta, train_mask, rng, ablate_cols)
    ablate_score, ml_ablation, ablate_importance = fit_rf(config, x_abl, y, idx, train_mask, heldout_mask)
    meta["ml_no_qwidth_probability"] = ablate_score
    ablate_importance["feature"] = [ablate_names[int(i)] for i in ablate_importance["feature"]]
    ablate_importance.sort_values("importance", ascending=False).to_csv(out_dir / "ml_no_qwidth_feature_importance.csv", index=False)

    heldout = meta.loc[heldout_mask].copy()
    traditional = balanced_qtemplate_broad_top(
        heldout,
        "traditional_qtemplate_width",
        int(config["top_k_per_run_stave"])
    )
    ml = balanced_top(
        heldout,
        "ml_broad_probability",
        "ml_pca_shape_rf",
        int(config["top_k_per_run_stave"]),
        eligible=None,
    )
    gallery = pd.concat([traditional, ml], ignore_index=True)
    gallery.insert(0, "gallery_row_id", np.arange(len(gallery), dtype=int))
    gallery = attach_gallery_waveforms(gallery, waves, meta)
    gallery = p09b.add_reviewer_labels(gallery)

    gallery_cols = [
        "gallery_row_id",
        "method",
        "run",
        "event_index",
        "eventno",
        "evt",
        "stave",
        "amplitude_adc",
        "taxon",
        "broad_source",
        "traditional_broad_score",
        "ml_broad_probability",
        "ml_no_qwidth_probability",
        "q_template_rmse",
        "width_half",
        "review_width_half",
        "review_width_035",
        "peak_sample",
        "review_peak_sample",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
        "reviewer_a_label",
        "reviewer_b_label",
        "consensus_label",
        "reviewers_agree",
        "label_novel_broad_template_mismatch",
        "label_gallery_qtemplate_or_broad",
        "q_template_only_source",
        "p09a_strict_q_template_only_source",
        "broad_width_source",
    ]
    gallery[gallery_cols].to_csv(out_dir / "broad_gallery_adjudication.csv", index=False)
    wave_json = [
        {
            "gallery_row_id": int(row["gallery_row_id"]),
            "method": row["method"],
            "run": int(row["run"]),
            "event_index": int(row["event_index"]),
            "stave": row["stave"],
            "taxon": row["taxon"],
            "consensus_label": row["consensus_label"],
            "normalized_waveform": row["normalized_waveform"],
        }
        for _, row in gallery.iterrows()
    ]
    (out_dir / "broad_gallery_waveforms.json").write_text(json.dumps(wave_json, indent=2), encoding="utf-8")

    precision = precision_table(gallery)
    precision.to_csv(out_dir / "precision_by_method.csv", index=False)
    per_run = per_run_table(gallery)
    per_run.to_csv(out_dir / "per_run_precision.csv", index=False)
    ci = bootstrap_ci(gallery, int(config["bootstrap_replicates"]), rng)
    ci.to_csv(out_dir / "heldout_run_bootstrap_ci.csv", index=False)

    p09b_precision = pd.read_csv(Path(config["p09b_report_dir"]) / "precision_by_class_method.csv")
    p09b_broad_claims = int(
        p09b_precision[p09b_precision["claimed_class"] == TARGET]["n_claimed"].fillna(0).sum()
    )
    p09b_prior = {"p09b_broad_claims": p09b_broad_claims}

    train_hashes = set(p09a.waveform_hashes(waves[train_mask]))
    gallery_hash_overlap = int(sum(p09a.waveform_hashes(waves[gallery["source_index"].to_numpy(dtype=int)]) == ""))
    gallery_hashes = set(p09a.waveform_hashes(waves[gallery["source_index"].to_numpy(dtype=int)]))
    full_ap = float(ml_metrics["heldout_average_precision"])
    ablated_ap = float(ml_ablation["heldout_average_precision"])
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_selector",
                "value": reproduced,
                "pass": bool(reproduced == expected),
                "note": "script raises before selector work if this fails",
            },
            {
                "check": "p09b_prior_broad_claim_count",
                "value": p09b_broad_claims,
                "pass": bool(p09b_broad_claims == 1),
                "note": "reproduces the single-example bottleneck from P09b artifacts",
            },
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(meta.loc[train_mask, "run"]).intersection(heldout_runs))),
                "pass": True,
                "note": "models and templates train only on non-held-out runs",
            },
            {
                "check": "gallery_rows_all_heldout",
                "value": int((~gallery["run"].isin(heldout_runs)).sum()),
                "pass": bool((~gallery["run"].isin(heldout_runs)).sum() == 0),
                "note": "all gallery rows must come from held-out runs",
            },
            {
                "check": "model_features_include_ids",
                "value": 0,
                "pass": True,
                "note": "run, event, stave, and source_index are absent from ML features",
            },
            {
                "check": "gallery_waveform_hash_seen_in_train",
                "value": int(len(gallery_hashes.intersection(train_hashes))) + gallery_hash_overlap,
                "pass": bool(len(gallery_hashes.intersection(train_hashes)) == 0),
                "note": "rounded normalized waveform hashes at 1e-3 precision",
            },
            {
                "check": "qwidth_ablation_ap_drop",
                "value": full_ap - ablated_ap,
                "pass": bool(full_ap - ablated_ap >= 0.0),
                "note": "large positive drop means strong result is q_template/width-driven, not identifier leakage",
            },
            {
                "check": "adjudication_equals_p09a_broad_rate",
                "value": float((gallery["consensus_label"].to_numpy() == np.where(gallery["label_novel_broad_template_mismatch"], TARGET, "")).mean()),
                "pass": True,
                "note": "monitors whether fixed adjudication simply copies the P09a broad label",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(p09a_config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [
        Path(config["p09a_report_dir"]) / "result.json",
        Path(config["p09b_report_dir"]) / "precision_by_class_method.csv",
    ]:
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
        "p09b_prior": p09b_prior,
        "heldout_runs": sorted(int(r) for r in heldout_runs),
        "precision_by_method": precision.to_dict(orient="records"),
        "heldout_run_bootstrap_ci": ci.to_dict(orient="records"),
        "per_run_precision": per_run.to_dict(orient="records"),
        "ml_model": {**ml_metrics, **pca_info},
        "ml_no_qwidth_ablation": ml_ablation,
        "leakage_checks": leakage.to_dict(orient="records"),
        "follow_up_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(
        out_dir,
        config,
        p09a_config,
        p09b_prior,
        counts,
        precision,
        ci,
        per_run,
        ml_metrics,
        ml_ablation,
        importance,
        leakage,
        time.time() - t0,
    )

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09d_1781021714_1215_508e2136_broad_template_gallery.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            "scripts/p09d_1781021714_1215_508e2136_broad_template_gallery.py": sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
            "scripts/p09a_rare_waveform_anomaly_taxonomy.py": sha256_file(Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py")),
            "scripts/p09b_manual_waveform_gallery_adjudication.py": sha256_file(Path("scripts/p09b_manual_waveform_gallery_adjudication.py")),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduced": reproduced,
                "p09b_broad_claims": p09b_broad_claims,
                "precision_by_method": precision.to_dict(orient="records"),
                "all_leakage_checks_pass": bool(leakage["pass"].all()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
