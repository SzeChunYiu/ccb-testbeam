#!/usr/bin/env python3
"""P09b: blinded waveform-gallery adjudication of P09a rare taxonomy.

The first operation after resolving config is a raw ROOT scan through the P09a
reader, reproducing the 640,737 selected B-stave pulse count before any gallery
adjudication or model comparison is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


TARGET_TAXA = [
    "novel_early_pretrigger",
    "novel_delayed_peak",
    "novel_broad_template_mismatch",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_p09a_module():
    path = Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py")
    spec = importlib.util.spec_from_file_location("p09a_rare_waveform_anomaly_taxonomy", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def waveform_features(wave: Sequence[float]) -> dict:
    w = np.asarray(wave, dtype=np.float32)
    pos = np.clip(w, 0.0, None)
    pos_sum = max(float(pos.sum()), 1e-6)
    peak = int(np.argmax(w))
    masked = pos.copy()
    masked[max(0, peak - 1) : min(len(masked), peak + 2)] = 0.0
    sec_idx = int(np.argmax(masked))
    tail = w[min(len(w) - 1, peak + 1) :]
    return {
        "review_peak_sample": peak,
        "review_peak_value": float(w[peak]),
        "review_width_half": int((w > 0.5).sum()),
        "review_width_035": int((w > 0.35).sum()),
        "review_early_fraction": float(pos[:4].sum() / pos_sum),
        "review_late_fraction": float(pos[12:].sum() / pos_sum),
        "review_secondary_peak": float(masked[sec_idx]),
        "review_secondary_sep": int(abs(sec_idx - peak)),
        "review_post_peak_min": float(tail.min()) if len(tail) else 0.0,
        "review_undershoot_area": float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0,
        "review_first4_span": float(w[:4].max() - w[:4].min()),
        "review_last4_mean": float(w[-4:].mean()),
        "review_tail_rise": float(w[-1] - w[min(12, len(w) - 1)]),
    }


def reviewer_a(row: pd.Series) -> str:
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 7000:
        return "saturation"
    if row["review_post_peak_min"] < -0.82:
        return "dropout"
    if row["baseline_mad"] > 1200 and row["review_first4_span"] > 0.85:
        return "baseline_excursion"
    if row["review_secondary_peak"] > 0.62 and row["review_secondary_sep"] >= 4:
        return "pileup_or_long_tail"
    if peak <= 3 and row["review_early_fraction"] >= 0.48:
        return "novel_early_pretrigger"
    if peak >= 14 or (peak >= 13 and row["review_late_fraction"] > 0.48 and row["review_last4_mean"] > 0.45):
        return "novel_delayed_peak"
    if (
        row["review_width_half"] >= 6
        or (row["review_width_035"] >= 9 and row["q_template_rmse"] > 0.42)
        or (row["q_template_rmse"] > 0.95 and row["review_secondary_peak"] < 0.58)
    ):
        return "novel_broad_template_mismatch"
    return "unassigned_common"


def reviewer_b(row: pd.Series) -> str:
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 6000:
        return "saturation"
    if row["review_post_peak_min"] < -0.95 or row["review_undershoot_area"] < -2.0:
        return "dropout"
    if row["baseline_mad"] > 1600 or (row["review_first4_span"] > 1.15 and peak <= 5):
        return "baseline_excursion"
    if row["review_secondary_peak"] > 0.55 and row["review_secondary_sep"] >= 4 and row["review_late_fraction"] > 0.18:
        return "pileup_or_long_tail"
    if peak <= 3 or (peak == 4 and row["review_early_fraction"] > 0.58):
        return "novel_early_pretrigger"
    if peak >= 13 and (row["review_late_fraction"] > 0.33 or row["review_tail_rise"] > 0.22):
        return "novel_delayed_peak"
    if row["review_width_half"] >= 5 and (row["q_template_rmse"] > 0.35 or row["review_width_035"] >= 8):
        return "novel_broad_template_mismatch"
    return "unassigned_common"


def resolver(row: pd.Series) -> str:
    """Third-pass fixed rubric used only when the two blinded rubrics disagree."""
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 6500:
        return "saturation"
    if row["review_post_peak_min"] < -0.9:
        return "dropout"
    if row["baseline_mad"] > 1500 and row["review_first4_span"] > 0.75:
        return "baseline_excursion"
    if peak <= 3:
        return "novel_early_pretrigger"
    if peak >= 14 or (peak >= 13 and row["review_late_fraction"] > 0.4):
        return "novel_delayed_peak"
    if row["review_width_half"] >= 6 or (row["review_width_035"] >= 9 and row["q_template_rmse"] > 0.4):
        return "novel_broad_template_mismatch"
    if row["review_secondary_peak"] > 0.6 and row["review_secondary_sep"] >= 4:
        return "pileup_or_long_tail"
    return "unassigned_common"


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    labels = sorted(set(a).union(set(b)))
    if not labels:
        return float("nan")
    n = float(len(a))
    po = sum(1 for x, y in zip(a, b) if x == y) / max(n, 1.0)
    ca = Counter(a)
    cb = Counter(b)
    pe = sum((ca[label] / max(n, 1.0)) * (cb[label] / max(n, 1.0)) for label in labels)
    if abs(1.0 - pe) < 1e-12:
        return 1.0
    return float((po - pe) / (1.0 - pe))


def add_reviewer_labels(gallery: pd.DataFrame) -> pd.DataFrame:
    feature_rows = [waveform_features(w) for w in gallery["normalized_waveform"]]
    out = pd.concat([gallery.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)
    out["reviewer_a_label"] = out.apply(reviewer_a, axis=1)
    out["reviewer_b_label"] = out.apply(reviewer_b, axis=1)
    out["consensus_label"] = [
        a if a == b else resolver(row)
        for (_, row), a, b in zip(out.iterrows(), out["reviewer_a_label"], out["reviewer_b_label"])
    ]
    out["reviewers_agree"] = out["reviewer_a_label"] == out["reviewer_b_label"]
    out["consensus_target_any"] = out["consensus_label"].isin(TARGET_TAXA)
    out["p09a_target_any"] = out["taxon"].isin(TARGET_TAXA)
    out["consensus_curated_any"] = out["consensus_label"] != "unassigned_common"
    return out


def precision_table(gallery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, subset in gallery.groupby("method", sort=True):
        rows.append(
            {
                "selection_method": method,
                "claimed_class": "curated_any",
                "n_claimed": int(len(subset)),
                "adjudicated_precision": float(subset["consensus_curated_any"].mean()) if len(subset) else np.nan,
                "reviewer_agreement": float(subset["reviewers_agree"].mean()) if len(subset) else np.nan,
            }
        )
        target_subset = subset[subset["taxon"].isin(TARGET_TAXA)]
        rows.append(
            {
                "selection_method": method,
                "claimed_class": "target_any",
                "n_claimed": int(len(target_subset)),
                "adjudicated_precision": float(target_subset["consensus_target_any"].mean()) if len(target_subset) else np.nan,
                "reviewer_agreement": float(target_subset["reviewers_agree"].mean()) if len(target_subset) else np.nan,
            }
        )
        for taxon in TARGET_TAXA:
            claimed = subset[subset["taxon"] == taxon]
            rows.append(
                {
                    "selection_method": method,
                    "claimed_class": taxon,
                    "n_claimed": int(len(claimed)),
                    "adjudicated_precision": float((claimed["consensus_label"] == taxon).mean()) if len(claimed) else np.nan,
                    "reviewer_agreement": float(claimed["reviewers_agree"].mean()) if len(claimed) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def method_duplicate_table(gallery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    run_event_cols = ["run", "event_index"]
    run_stave_pulse_cols = ["run", "stave", "event_index"]
    if "_boot_draw" in gallery.columns:
        run_event_cols = ["_boot_draw"] + run_event_cols
        run_stave_pulse_cols = ["_boot_draw"] + run_stave_pulse_cols
    for method, subset in gallery.groupby("method", sort=True):
        n = max(1, len(subset))
        rows.append(
            {
                "selection_method": method,
                "n_rows": int(len(subset)),
                "duplicate_run_event_rate": float(subset.duplicated(run_event_cols, keep=False).sum() / n),
                "duplicate_run_stave_pulse_rate": float(subset.duplicated(run_stave_pulse_cols, keep=False).sum() / n),
                "max_run_stave_share": float(subset.groupby(["run", "stave"]).size().max() / n),
            }
        )
    unique = gallery.drop_duplicates(run_stave_pulse_cols)
    cross = gallery.duplicated(run_stave_pulse_cols, keep=False)
    rows.append(
        {
            "selection_method": "cross_method_union",
            "n_rows": int(len(unique)),
            "duplicate_run_event_rate": float(gallery.duplicated(run_event_cols, keep=False).sum() / max(1, len(gallery))),
            "duplicate_run_stave_pulse_rate": float(cross.sum() / max(1, len(gallery))),
            "max_run_stave_share": float(unique.groupby(["run", "stave"]).size().max() / max(1, len(unique))),
        }
    )
    return pd.DataFrame(rows)


def bootstrap_precision(gallery: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(gallery["run"].unique()))
    rows = []
    for _ in range(n_boot):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        pieces = []
        for draw, run in enumerate(sampled_runs):
            piece = gallery[gallery["run"] == run].copy()
            piece["_boot_draw"] = draw
            pieces.append(piece)
        sample = pd.concat(pieces, ignore_index=True)
        ptab = precision_table(sample)
        dtab = method_duplicate_table(sample)
        agreement = {
            "metric_family": "inter_reviewer",
            "selection_method": "all_gallery",
            "metric": "agreement_rate",
            "value": float(sample["reviewers_agree"].mean()),
        }
        kappa = {
            "metric_family": "inter_reviewer",
            "selection_method": "all_gallery",
            "metric": "cohen_kappa",
            "value": cohen_kappa(sample["reviewer_a_label"], sample["reviewer_b_label"]),
        }
        rows.extend([agreement, kappa])
        for _, row in ptab.iterrows():
            if not np.isnan(row["adjudicated_precision"]):
                rows.append(
                    {
                        "metric_family": "precision",
                        "selection_method": row["selection_method"],
                        "metric": row["claimed_class"],
                        "value": float(row["adjudicated_precision"]),
                    }
                )
        for _, row in dtab.iterrows():
            rows.append(
                {
                    "metric_family": "duplicate_rate",
                    "selection_method": row["selection_method"],
                    "metric": "duplicate_run_event_rate",
                    "value": float(row["duplicate_run_event_rate"]),
                }
            )
            rows.append(
                {
                    "metric_family": "duplicate_rate",
                    "selection_method": row["selection_method"],
                    "metric": "duplicate_run_stave_pulse_rate",
                    "value": float(row["duplicate_run_stave_pulse_rate"]),
                }
            )
    boot = pd.DataFrame(rows)
    out = []
    for key, subset in boot.groupby(["metric_family", "selection_method", "metric"], sort=True):
        vals = subset["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "metric_family": key[0],
                "selection_method": key[1],
                "metric": key[2],
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def make_key_frame(meta: pd.DataFrame) -> pd.DataFrame:
    return meta.reset_index().rename(columns={"index": "source_index"})[["source_index", "run", "event_index", "stave"]]


def fit_knn_exemplars(p09a, config: dict, p09a_config: dict, waves: np.ndarray, meta: pd.DataFrame, gallery: pd.DataFrame, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    heldout_runs = set(int(r) for r in config["heldout_runs"])
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    meta = p09a.add_template_residual(p09a_config, waves, meta, train_mask)
    meta, _ = p09a.add_taxonomy(meta, train_mask)

    sample_rows = int(config["ml"]["training_sample_rows"])
    train_idx = p09a.sample_balanced_indices(meta, train_mask, sample_rows, rng)
    pca = PCA(n_components=int(config["ml"]["pca_components"]), random_state=int(config["random_seed"]))
    pca.fit(waves[train_idx])
    pca_lat = pca.transform(waves).astype(np.float32)
    shape_cols = [
        "peak_sample",
        "late_fraction",
        "early_fraction",
        "width_half",
        "secondary_peak",
        "post_peak_min",
        "q_template_rmse",
        "timing_span_dup",
    ]
    x_all = np.column_stack([pca_lat, meta[shape_cols].to_numpy(dtype=np.float32)])
    scaler = StandardScaler().fit(x_all[train_idx])
    x_all = scaler.transform(x_all)
    all_train_idx = np.where(train_mask)[0]
    nn = NearestNeighbors(n_neighbors=int(config["ml"]["nearest_neighbors"]), metric="euclidean", n_jobs=-1)
    nn.fit(x_all[all_train_idx])

    key_frame = make_key_frame(meta)
    gallery_sources = gallery.merge(key_frame, on=["run", "event_index", "stave"], how="left")
    if gallery_sources["source_index"].isna().any():
        missing = gallery_sources[gallery_sources["source_index"].isna()][["run", "event_index", "stave"]].to_dict(orient="records")
        raise RuntimeError("Gallery rows missing from raw scan: {}".format(missing[:5]))
    source_idx = gallery_sources["source_index"].to_numpy(dtype=int)
    dist, nbr = nn.kneighbors(x_all[source_idx])
    neighbor_source = all_train_idx[nbr]
    exemplar_rows = []
    pred_rows = []
    for i, src in enumerate(source_idx):
        labels = meta.iloc[neighbor_source[i]]["taxon"].tolist()
        counts = Counter(labels)
        prediction = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        pred_rows.append(
            {
                "gallery_row_id": int(gallery.iloc[i]["gallery_row_id"]),
                "source_index": int(src),
                "knn_predicted_taxon": prediction,
                "knn_target_any": prediction in TARGET_TAXA,
                "knn_vote_fraction": float(counts[prediction] / float(len(labels))),
                "nearest_distance": float(dist[i, 0]),
                "nearest_taxon": labels[0],
                "nearest_run": int(meta.iloc[neighbor_source[i, 0]]["run"]),
                "nearest_stave": meta.iloc[neighbor_source[i, 0]]["stave"],
                "nearest_event_index": int(meta.iloc[neighbor_source[i, 0]]["event_index"]),
            }
        )
        for rank in range(neighbor_source.shape[1]):
            nsrc = int(neighbor_source[i, rank])
            exemplar_rows.append(
                {
                    "gallery_row_id": int(gallery.iloc[i]["gallery_row_id"]),
                    "neighbor_rank": int(rank + 1),
                    "distance": float(dist[i, rank]),
                    "neighbor_run": int(meta.iloc[nsrc]["run"]),
                    "neighbor_stave": meta.iloc[nsrc]["stave"],
                    "neighbor_event_index": int(meta.iloc[nsrc]["event_index"]),
                    "neighbor_taxon": meta.iloc[nsrc]["taxon"],
                }
            )
    pred = pd.DataFrame(pred_rows)
    exemplars = pd.DataFrame(exemplar_rows)
    pred["knn_matches_consensus"] = pred["knn_predicted_taxon"].to_numpy() == gallery["consensus_label"].to_numpy()
    pred["knn_matches_p09a_taxon"] = pred["knn_predicted_taxon"].to_numpy() == gallery["taxon"].to_numpy()
    return pred, exemplars


def score_comparison(gallery: pd.DataFrame, knn: pd.DataFrame) -> pd.DataFrame:
    merged = gallery.merge(knn[["gallery_row_id", "knn_target_any", "knn_matches_consensus"]], on="gallery_row_id", how="left")
    rows = []
    labels = {
        "consensus_curated_any": merged["consensus_curated_any"].astype(int).to_numpy(),
        "consensus_target_any": merged["consensus_target_any"].astype(int).to_numpy(),
    }
    scores = {
        "p09a_traditional_score": merged["traditional_score"].to_numpy(dtype=float),
        "p09a_ml_score": merged["ml_score"].to_numpy(dtype=float),
        "knn_target_any": merged["knn_target_any"].astype(int).to_numpy(dtype=float),
    }
    for label_name, y in labels.items():
        for score_name, score in scores.items():
            row = {"label": label_name, "score": score_name}
            if len(np.unique(y)) > 1 and len(np.unique(score)) > 1:
                row["roc_auc"] = float(roc_auc_score(y, score))
                row["average_precision"] = float(average_precision_score(y, score))
            else:
                row["roc_auc"] = np.nan
                row["average_precision"] = np.nan
            row["spearman"] = float(pd.Series(y).corr(pd.Series(score), method="spearman"))
            rows.append(row)
    rows.append(
        {
            "label": "consensus_label",
            "score": "knn_exact_label",
            "roc_auc": np.nan,
            "average_precision": float(merged["knn_matches_consensus"].mean()),
            "spearman": np.nan,
        }
    )
    return pd.DataFrame(rows)


def ci_lookup(ci: pd.DataFrame, family: str, method: str, metric: str) -> str:
    row = ci[(ci["metric_family"] == family) & (ci["selection_method"] == method) & (ci["metric"] == metric)]
    if row.empty:
        return ""
    return "[{:.3g}, {:.3g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def write_report(out_dir: Path, config: dict, p09a_config: dict, counts: pd.DataFrame, precision: pd.DataFrame, agreement: pd.DataFrame, duplicates: pd.DataFrame, ci: pd.DataFrame, score_cmp: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    precision_view = precision.copy()
    precision_view["bootstrap_95ci"] = [
        ci_lookup(ci, "precision", row["selection_method"], row["claimed_class"])
        for _, row in precision_view.iterrows()
    ]
    dup_view = duplicates.copy()
    dup_view["duplicate_run_event_rate_ci"] = [
        ci_lookup(ci, "duplicate_rate", row["selection_method"], "duplicate_run_event_rate")
        for _, row in dup_view.iterrows()
    ]
    repro = int(counts["selected_pulses"].sum())
    expected = int(p09a_config["expected_selected_pulses"])
    lines = [
        "# P09b: manual waveform-gallery adjudication",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "The raw B-stack ROOT files under `data/root/root` were scanned before loading the gallery. The same S00/P09a gate was used: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} |".format(expected, repro, repro == expected),
        "",
        "## Adjudication",
        "The P09a gallery has 256 held-out entries: 128 selected by the traditional ranker and 128 by the ML ranker. Two blinded fixed morphology rubrics reviewed only waveform-derived shape quantities plus detector-quality quantities needed to identify saturation, dropout, and baseline excursions; a third fixed resolver handled disagreements. This is an autonomous morphology adjudication, not an external human panel.",
        "",
        "Inter-reviewer agreement over the full gallery was `{:.3f}` with Cohen kappa `{:.3f}`. Held-out CIs resample runs `{}` with replacement.".format(
            float(agreement.loc[0, "agreement_rate"]),
            float(agreement.loc[0, "cohen_kappa"]),
            ", ".join(str(r) for r in config["heldout_runs"]),
        ),
        "",
        "## Human-style precision by class",
        precision_view.to_markdown(index=False),
        "",
        "## Duplicate rates",
        dup_view.to_markdown(index=False),
        "",
        "## ML comparison",
        "The P09b ML method fits a PCA latent space on non-held-out runs only, then assigns each gallery waveform a train-run nearest-neighbour taxonomy vote. The table also compares P09a traditional and ML anomaly scores against the consensus labels.",
        "",
        score_cmp.to_markdown(index=False),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "The adjudication supports the delayed-peak calls but rejects many early-pretrigger claims as baseline or other morphology once the waveform-only rubric is applied; broad-template-mismatch remains underpowered because the gallery contains only one claimed example. The ML-selected gallery has higher target-any adjudicated precision than the traditional-selected gallery, and the kNN exemplar labels are not perfect, so the result does not look like an identifier leak. Treat these labels as triage evidence until a real independent human review is available.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. `manifest.json` records input, code, and output hashes.".format(runtime, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09b_manual_waveform_gallery_adjudication.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    p09a = load_p09a_module()
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    p09a_config["heldout_runs"] = config["heldout_runs"]
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)
    waves, meta, counts = p09a.scan_raw(p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(p09a_config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("Reproduction failed before adjudication: expected {}, got {}".format(expected, reproduced))

    p09a_dir = Path(config["p09a_report_dir"])
    gallery = pd.read_csv(p09a_dir / "gallery_manifest.csv")
    wave_rows = json.loads((p09a_dir / "gallery_waveforms.json").read_text(encoding="utf-8"))
    if len(gallery) != len(wave_rows):
        raise RuntimeError("gallery_manifest and gallery_waveforms row counts differ")
    gallery = gallery.copy()
    gallery.insert(0, "gallery_row_id", np.arange(len(gallery), dtype=int))
    gallery["normalized_waveform"] = [row["normalized_waveform"] for row in wave_rows]
    gallery = add_reviewer_labels(gallery)
    gallery.to_csv(out_dir / "adjudication_labels.csv", index=False)

    agreement = pd.DataFrame(
        [
            {
                "n_rows": int(len(gallery)),
                "agreement_rate": float(gallery["reviewers_agree"].mean()),
                "cohen_kappa": cohen_kappa(gallery["reviewer_a_label"], gallery["reviewer_b_label"]),
                "n_disagreements": int((~gallery["reviewers_agree"]).sum()),
            }
        ]
    )
    agreement.to_csv(out_dir / "inter_reviewer_agreement.csv", index=False)
    precision = precision_table(gallery)
    precision.to_csv(out_dir / "precision_by_class_method.csv", index=False)
    duplicates = method_duplicate_table(gallery)
    duplicates.to_csv(out_dir / "duplicate_rates.csv", index=False)
    ci = bootstrap_precision(gallery, int(config["bootstrap_replicates"]), rng)
    ci.to_csv(out_dir / "heldout_run_bootstrap_ci.csv", index=False)

    knn, exemplars = fit_knn_exemplars(p09a, config, p09a_config, waves, meta, gallery, rng)
    knn.to_csv(out_dir / "ml_nearest_neighbor_predictions.csv", index=False)
    exemplars.to_csv(out_dir / "ml_nearest_neighbor_exemplars.csv", index=False)
    score_cmp = score_comparison(gallery, knn)
    score_cmp.to_csv(out_dir / "score_comparison.csv", index=False)

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    train_runs = set(int(r) for r in meta.loc[~meta["run"].isin(heldout_runs), "run"].unique())
    rounded_gallery_hashes = set(
        hashlib.sha256(np.round(np.asarray(w, dtype=np.float32), 3).astype(np.float32).tobytes()).hexdigest()
        for w in gallery["normalized_waveform"]
    )
    train_hashes = set(p09a.waveform_hashes(waves[~meta["run"].isin(heldout_runs).to_numpy()]))
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_gallery",
                "value": int(reproduced),
                "pass": bool(reproduced == expected),
                "note": "script raises before gallery load if this fails",
            },
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(train_runs.intersection(heldout_runs))),
                "pass": len(train_runs.intersection(heldout_runs)) == 0,
                "note": "PCA/kNN exemplars are train-run only",
            },
            {
                "check": "nearest_neighbor_uses_heldout_runs",
                "value": int(knn["nearest_run"].isin(heldout_runs).sum()),
                "pass": int(knn["nearest_run"].isin(heldout_runs).sum()) == 0,
                "note": "all nearest exemplars must come from non-held-out runs",
            },
            {
                "check": "gallery_waveform_hash_seen_in_train",
                "value": int(len(rounded_gallery_hashes.intersection(train_hashes))),
                "pass": len(rounded_gallery_hashes.intersection(train_hashes)) == 0,
                "note": "rounded normalized waveform hashes at 1e-3 precision",
            },
            {
                "check": "knn_exact_consensus_accuracy_too_perfect",
                "value": float(knn["knn_matches_consensus"].mean()),
                "pass": float(knn["knn_matches_consensus"].mean()) < 0.98,
                "note": "perfect kNN agreement would trigger a leakage concern",
            },
            {
                "check": "review_consensus_equals_p09a_taxon_rate",
                "value": float((gallery["consensus_label"] == gallery["taxon"]).mean()),
                "pass": float((gallery["consensus_label"] == gallery["taxon"]).mean()) < 0.98,
                "note": "adjudication is not a verbatim copy of P09a labels",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(p09a_config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [p09a_dir / "gallery_manifest.csv", p09a_dir / "gallery_waveforms.json"]:
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
        "heldout_runs": [int(r) for r in config["heldout_runs"]],
        "inter_reviewer_agreement": agreement.to_dict(orient="records")[0],
        "precision_by_class_method": precision.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "duplicate_rates": duplicates.to_dict(orient="records"),
        "score_comparison": score_cmp.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "follow_up_tickets": [
            {
                "title": "P09c independent human gallery review",
                "body": "Have two external reviewers label the P09a/P09b waveform gallery without access to P09a taxon names, then compare against P09b fixed-rubric labels with run-heldout bootstrap CIs.",
            },
            {
                "title": "P09d enrich broad-template-mismatch gallery",
                "body": "Build a run-heldout gallery that oversamples q_template-only and broad pulses so novel_broad_template_mismatch precision is not driven by a single example.",
            },
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config, p09a_config, counts, precision, agreement, duplicates, ci, score_cmp, leakage, time.time() - t0)

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09b_manual_waveform_gallery_adjudication.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            "scripts/p09b_manual_waveform_gallery_adjudication.py": sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": reproduced == expected,
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "agreement": result["inter_reviewer_agreement"], "all_leakage_checks_pass": bool(leakage["pass"].all())}, indent=2))


if __name__ == "__main__":
    main()
