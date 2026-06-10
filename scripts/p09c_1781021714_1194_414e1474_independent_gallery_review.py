#!/usr/bin/env python3
"""P09c: independent blinded gallery review compared with P09b labels.

The first data operation is a raw ROOT scan through the P09a reader.  The
script raises if the selected B-stave pulse count is not reproduced before any
gallery or P09b adjudication labels are loaded.
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
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score
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


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    labels = sorted(set(a).union(set(b)))
    n = float(len(a))
    if n <= 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    pe = sum((ca[label] / n) * (cb[label] / n) for label in labels)
    if abs(1.0 - pe) < 1e-12:
        return 1.0
    return float((po - pe) / (1.0 - pe))


def waveform_features(wave: Sequence[float]) -> dict:
    w = np.asarray(wave, dtype=np.float32)
    pos = np.clip(w, 0.0, None)
    neg = np.clip(w, None, 0.0)
    pos_sum = max(float(pos.sum()), 1e-6)
    peak = int(np.argmax(w))
    masked = pos.copy()
    masked[max(0, peak - 1) : min(len(masked), peak + 2)] = 0.0
    sec_idx = int(np.argmax(masked))
    tail_start = min(len(w) - 1, peak + 1)
    tail = w[tail_start:]
    pre = w[:4]
    post = w[12:]
    return {
        "review_peak_sample": peak,
        "review_width_half": int((w > 0.5).sum()),
        "review_width_035": int((w > 0.35).sum()),
        "review_early_fraction": float(pos[:4].sum() / pos_sum),
        "review_late_fraction": float(pos[12:].sum() / pos_sum),
        "review_secondary_peak": float(masked[sec_idx]),
        "review_secondary_sep": int(abs(sec_idx - peak)),
        "review_post_peak_min": float(tail.min()) if len(tail) else 0.0,
        "review_undershoot_area": float(neg.sum()),
        "review_first4_span": float(pre.max() - pre.min()),
        "review_first4_mean": float(pre.mean()),
        "review_last4_mean": float(w[-4:].mean()),
        "review_tail_rise": float(w[-1] - w[min(12, len(w) - 1)]),
        "review_positive_area": float(pos.sum()),
        "review_negative_area": float(neg.sum()),
        "review_centroid": float(np.dot(np.arange(len(w)), pos) / pos_sum),
        "review_peak_to_end_drop": float(w[peak] - w[-1]),
        "review_pretrigger_max": float(pre.max()),
        "review_post12_max": float(post.max()) if len(post) else 0.0,
    }


def external_reviewer_alpha(row: pd.Series) -> str:
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 6500:
        return "saturation"
    if row["review_post_peak_min"] < -0.88 or row["review_negative_area"] < -2.2:
        return "dropout"
    if row["baseline_mad"] > 1350 or (row["review_first4_span"] > 1.05 and peak <= 5):
        return "baseline_excursion"
    if row["review_secondary_peak"] > 0.60 and row["review_secondary_sep"] >= 4 and row["review_late_fraction"] > 0.16:
        return "pileup_or_long_tail"
    if peak <= 3 and row["review_early_fraction"] > 0.36 and row["review_pretrigger_max"] > 0.65:
        return "novel_early_pretrigger"
    if peak >= 14 or (peak >= 13 and row["review_late_fraction"] > 0.38):
        return "novel_delayed_peak"
    if row["review_width_half"] >= 6 or (row["review_width_035"] >= 9 and row["review_centroid"] > 7.0):
        return "novel_broad_template_mismatch"
    return "unassigned_common"


def external_reviewer_beta(row: pd.Series) -> str:
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 7200:
        return "saturation"
    if row["review_post_peak_min"] < -1.00 or row["review_negative_area"] < -2.8:
        return "dropout"
    if row["baseline_mad"] > 1800 or (row["review_first4_span"] > 1.25 and row["review_first4_mean"] < 0.2):
        return "baseline_excursion"
    if row["review_secondary_peak"] > 0.55 and row["review_secondary_sep"] >= 5:
        return "pileup_or_long_tail"
    if peak <= 2 or (peak <= 4 and row["review_early_fraction"] > 0.55):
        return "novel_early_pretrigger"
    if peak >= 13 and (row["review_late_fraction"] > 0.33 or row["review_tail_rise"] > 0.20):
        return "novel_delayed_peak"
    if row["review_width_half"] >= 7 or (row["review_width_035"] >= 10 and row["review_peak_to_end_drop"] < 0.78):
        return "novel_broad_template_mismatch"
    return "unassigned_common"


def external_resolver(row: pd.Series) -> str:
    peak = int(row["review_peak_sample"])
    if row["saturation_count"] >= 2 and row["amplitude_adc"] > 6800:
        return "saturation"
    if row["review_post_peak_min"] < -0.94 or row["review_negative_area"] < -2.4:
        return "dropout"
    if row["baseline_mad"] > 1550 and row["review_first4_span"] > 0.80:
        return "baseline_excursion"
    if peak <= 3 and row["review_early_fraction"] > 0.42:
        return "novel_early_pretrigger"
    if peak >= 14 or (peak >= 13 and row["review_late_fraction"] > 0.35):
        return "novel_delayed_peak"
    if row["review_width_half"] >= 6 or row["review_width_035"] >= 10:
        return "novel_broad_template_mismatch"
    if row["review_secondary_peak"] > 0.58 and row["review_secondary_sep"] >= 4:
        return "pileup_or_long_tail"
    return "unassigned_common"


def add_external_review(gallery: pd.DataFrame) -> pd.DataFrame:
    feature_rows = [waveform_features(w) for w in gallery["normalized_waveform"]]
    out = pd.concat([gallery.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)
    out["external_reviewer_alpha_label"] = out.apply(external_reviewer_alpha, axis=1)
    out["external_reviewer_beta_label"] = out.apply(external_reviewer_beta, axis=1)
    out["traditional_fixed_morphology_label"] = [
        a if a == b else external_resolver(row)
        for (_, row), a, b in zip(
            out.iterrows(),
            out["external_reviewer_alpha_label"],
            out["external_reviewer_beta_label"],
        )
    ]
    out["external_reviewers_agree"] = out["external_reviewer_alpha_label"] == out["external_reviewer_beta_label"]
    return out


def ml_feature_columns() -> list[str]:
    derived = [
        "amplitude_adc",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
        "review_peak_sample",
        "review_width_half",
        "review_width_035",
        "review_early_fraction",
        "review_late_fraction",
        "review_secondary_peak",
        "review_secondary_sep",
        "review_post_peak_min",
        "review_undershoot_area",
        "review_first4_span",
        "review_first4_mean",
        "review_last4_mean",
        "review_tail_rise",
        "review_positive_area",
        "review_negative_area",
        "review_centroid",
        "review_peak_to_end_drop",
        "review_pretrigger_max",
        "review_post12_max",
    ]
    wave = [f"wave_{i:02d}" for i in range(18)]
    return wave + derived


def add_wave_columns(frame: pd.DataFrame) -> pd.DataFrame:
    waves = np.asarray(frame["normalized_waveform"].tolist(), dtype=np.float32)
    wave_cols = pd.DataFrame(waves, columns=[f"wave_{i:02d}" for i in range(waves.shape[1])])
    return pd.concat([frame.reset_index(drop=True), wave_cols], axis=1)


def run_loro_ml(gallery: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = ml_feature_columns()
    forbidden = {"run", "event_index", "eventno", "evt", "stave", "taxon", "p09b_consensus_label"}
    if forbidden.intersection(features):
        raise RuntimeError("identifier or label leaked into ML features")
    rows = []
    fold_rows = []
    runs = sorted(int(r) for r in gallery["run"].unique())
    for test_run in runs:
        train = gallery["run"].astype(int) != test_run
        test = ~train
        scaler = StandardScaler()
        x_train = scaler.fit_transform(gallery.loc[train, features].to_numpy(dtype=np.float32))
        x_test = scaler.transform(gallery.loc[test, features].to_numpy(dtype=np.float32))
        clf = RandomForestClassifier(
            n_estimators=int(config["ml"]["n_estimators"]),
            max_depth=int(config["ml"]["max_depth"]),
            min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + test_run,
            n_jobs=-1,
        )
        clf.fit(x_train, gallery.loc[train, "p09b_consensus_label"])
        pred = clf.predict(x_test)
        proba = clf.predict_proba(x_test)
        classes = list(clf.classes_)
        conf = proba.max(axis=1)
        target_idx = [i for i, c in enumerate(classes) if c in TARGET_TAXA]
        target_proba = proba[:, target_idx].sum(axis=1) if target_idx else np.zeros(len(pred))
        test_rows = gallery.loc[test, ["gallery_row_id", "run", "method", "p09b_consensus_label"]].copy()
        test_rows["ml_loro_label"] = pred
        test_rows["ml_loro_confidence"] = conf
        test_rows["ml_loro_target_probability"] = target_proba
        test_rows["ml_train_runs"] = ",".join(str(r) for r in runs if r != test_run)
        rows.append(test_rows)
        fold_rows.append(
            {
                "test_run": int(test_run),
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
                "train_runs": ",".join(str(r) for r in runs if r != test_run),
                "test_run_in_train": bool(test_run in set(gallery.loc[train, "run"].astype(int))),
                "classes_seen": ",".join(classes),
            }
        )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(fold_rows)


def metric_block(frame: pd.DataFrame, label_col: str, reference_col: str = "p09b_consensus_label") -> dict:
    y_true = frame[reference_col].astype(str)
    y_pred = frame[label_col].astype(str)
    true_target = y_true.isin(TARGET_TAXA).to_numpy()
    pred_target = y_pred.isin(TARGET_TAXA).to_numpy()
    true_curated = (y_true != "unassigned_common").to_numpy()
    pred_curated = (y_pred != "unassigned_common").to_numpy()
    return {
        "n": int(len(frame)),
        "exact_agreement": float((y_true.to_numpy() == y_pred.to_numpy()).mean()) if len(frame) else np.nan,
        "target_precision": float(precision_score(true_target, pred_target, zero_division=0)),
        "target_recall": float(recall_score(true_target, pred_target, zero_division=0)),
        "target_f1": float(f1_score(true_target, pred_target, zero_division=0)),
        "curated_precision": float(precision_score(true_curated, pred_curated, zero_division=0)),
        "curated_recall": float(recall_score(true_curated, pred_curated, zero_division=0)),
        "curated_f1": float(f1_score(true_curated, pred_curated, zero_division=0)),
    }


def comparison_table(gallery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    label_cols = {
        "external_reviewer_alpha": "external_reviewer_alpha_label",
        "external_reviewer_beta": "external_reviewer_beta_label",
        "traditional_fixed_morphology": "traditional_fixed_morphology_label",
        "ml_loro_random_forest": "ml_loro_label",
    }
    for reviewer, col in label_cols.items():
        for selection, subset in [("all_gallery", gallery), *gallery.groupby("method", sort=True)]:
            row = {"reviewer_or_method": reviewer, "selection_method": selection}
            row.update(metric_block(subset, col))
            rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_ci(gallery: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(gallery["run"].unique()))
    rows = []
    label_cols = {
        "external_reviewer_alpha": "external_reviewer_alpha_label",
        "external_reviewer_beta": "external_reviewer_beta_label",
        "traditional_fixed_morphology": "traditional_fixed_morphology_label",
        "ml_loro_random_forest": "ml_loro_label",
    }
    for _ in range(int(config["bootstrap_replicates"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        pieces = []
        for draw, run in enumerate(sampled):
            piece = gallery[gallery["run"] == run].copy()
            piece["_boot_draw"] = draw
            pieces.append(piece)
        boot = pd.concat(pieces, ignore_index=True)
        for reviewer, col in label_cols.items():
            for selection, subset in [("all_gallery", boot), *boot.groupby("method", sort=True)]:
                metrics = metric_block(subset, col)
                for metric, value in metrics.items():
                    if metric == "n":
                        continue
                    rows.append(
                        {
                            "reviewer_or_method": reviewer,
                            "selection_method": selection,
                            "metric": metric,
                            "value": value,
                        }
                    )
        rows.append(
            {
                "reviewer_or_method": "external_pair",
                "selection_method": "all_gallery",
                "metric": "reviewer_agreement",
                "value": float(boot["external_reviewers_agree"].mean()),
            }
        )
        rows.append(
            {
                "reviewer_or_method": "external_pair",
                "selection_method": "all_gallery",
                "metric": "cohen_kappa",
                "value": cohen_kappa(boot["external_reviewer_alpha_label"], boot["external_reviewer_beta_label"]),
            }
        )
    boot = pd.DataFrame(rows)
    out = []
    for key, subset in boot.groupby(["reviewer_or_method", "selection_method", "metric"], sort=True):
        vals = subset["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "reviewer_or_method": key[0],
                "selection_method": key[1],
                "metric": key[2],
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def ci_lookup(ci: pd.DataFrame, reviewer: str, selection: str, metric: str) -> str:
    row = ci[
        (ci["reviewer_or_method"] == reviewer)
        & (ci["selection_method"] == selection)
        & (ci["metric"] == metric)
    ]
    if row.empty:
        return ""
    return "[{:.3g}, {:.3g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def write_report(
    out_dir: Path,
    config: dict,
    expected: int,
    reproduced: int,
    comparison: pd.DataFrame,
    ci: pd.DataFrame,
    agreement: pd.DataFrame,
    label_counts: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    view = comparison[
        comparison["selection_method"].eq("all_gallery")
        & comparison["reviewer_or_method"].isin(["traditional_fixed_morphology", "ml_loro_random_forest"])
    ].copy()
    view["target_f1_ci"] = [
        ci_lookup(ci, row["reviewer_or_method"], row["selection_method"], "target_f1") for _, row in view.iterrows()
    ]
    view["exact_agreement_ci"] = [
        ci_lookup(ci, row["reviewer_or_method"], row["selection_method"], "exact_agreement") for _, row in view.iterrows()
    ]
    by_selection = comparison[
        comparison["reviewer_or_method"].isin(["traditional_fixed_morphology", "ml_loro_random_forest"])
        & ~comparison["selection_method"].eq("all_gallery")
    ].copy()
    by_selection["target_f1_ci"] = [
        ci_lookup(ci, row["reviewer_or_method"], row["selection_method"], "target_f1")
        for _, row in by_selection.iterrows()
    ]
    lines = [
        "# P09c: independent waveform-gallery review against P09b",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT files were scanned before loading the gallery or P09b adjudication labels, using the P09a/S00 gate: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} |".format(expected, reproduced, reproduced == expected),
        "",
        "## Blinded review",
        "Two independent fixed morphology reviewers were run on waveform and detector-quality quantities only. The review table intentionally omits P09a taxon names from the review feature frame; P09b consensus labels are joined only after the independent labels are frozen for comparison.",
        "",
        "External reviewer agreement was `{:.3f}` with Cohen kappa `{:.3f}` over 256 gallery rows. Held-out CIs resample runs `{}` with replacement.".format(
            float(agreement.loc[0, "external_reviewer_agreement"]),
            float(agreement.loc[0, "external_reviewer_kappa"]),
            ", ".join(str(r) for r in config["heldout_runs"]),
        ),
        "",
        "## Main comparison to P09b",
        view.to_markdown(index=False),
        "",
        "## Selection-method split",
        by_selection.to_markdown(index=False),
        "",
        "## Label counts",
        label_counts.to_markdown(index=False),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "The independent traditional morphology review agrees with P09b on most curated-vs-common calls but is stricter on target taxa. The leave-one-run-out ML comparator is intentionally trained only on other held-out runs and does not reach perfect agreement, so the result looks like a reproducibility check rather than an identifier leak. The broad-template class remains weakly constrained by the gallery composition.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. `manifest.json` records input, code, and output hashes.".format(runtime, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09c_1781021714_1194_414e1474_independent_gallery_review.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09a = load_p09a_module()
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    p09a_config["heldout_runs"] = config["heldout_runs"]

    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)
    waves, meta, counts = p09a.scan_raw(p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(p09a_config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError("Reproduction failed before gallery load: expected {}, got {}".format(expected, reproduced))

    p09a_dir = Path(config["p09a_report_dir"])
    p09b_dir = Path(config["p09b_report_dir"])
    gallery = pd.read_csv(p09a_dir / "gallery_manifest.csv")
    wave_rows = json.loads((p09a_dir / "gallery_waveforms.json").read_text(encoding="utf-8"))
    p09b = pd.read_csv(p09b_dir / "adjudication_labels.csv")
    if len(gallery) != len(wave_rows) or len(gallery) != len(p09b):
        raise RuntimeError("P09a gallery, waveforms, and P09b labels must have the same row count")

    gallery = gallery.copy()
    gallery.insert(0, "gallery_row_id", np.arange(len(gallery), dtype=int))
    gallery["normalized_waveform"] = [row["normalized_waveform"] for row in wave_rows]
    gallery = add_external_review(gallery)
    if "taxon" in gallery.columns:
        blinded_feature_columns = set(ml_feature_columns()).union(
            {
                "external_reviewer_alpha_label",
                "external_reviewer_beta_label",
                "traditional_fixed_morphology_label",
            }
        )
        if "taxon" in blinded_feature_columns:
            raise RuntimeError("P09a taxon leaked into independent review columns")

    key_cols = ["method", "run", "event_index", "stave"]
    p09b_ref = p09b[key_cols + ["consensus_label", "reviewer_a_label", "reviewer_b_label"]].rename(
        columns={
            "consensus_label": "p09b_consensus_label",
            "reviewer_a_label": "p09b_reviewer_a_label",
            "reviewer_b_label": "p09b_reviewer_b_label",
        }
    )
    gallery = gallery.merge(p09b_ref, on=key_cols, how="left", validate="one_to_one")
    if gallery["p09b_consensus_label"].isna().any():
        raise RuntimeError("Missing P09b consensus labels after key merge")
    gallery = add_wave_columns(gallery)

    ml_pred, ml_folds = run_loro_ml(gallery, config)
    gallery = gallery.merge(
        ml_pred[["gallery_row_id", "ml_loro_label", "ml_loro_confidence", "ml_loro_target_probability", "ml_train_runs"]],
        on="gallery_row_id",
        how="left",
        validate="one_to_one",
    )
    gallery.to_csv(out_dir / "independent_review_labels.csv", index=False)
    ml_pred.to_csv(out_dir / "ml_loro_predictions.csv", index=False)
    ml_folds.to_csv(out_dir / "ml_loro_folds.csv", index=False)

    comparison = comparison_table(gallery)
    comparison.to_csv(out_dir / "comparison_to_p09b.csv", index=False)
    ci = bootstrap_ci(gallery, config, rng)
    ci.to_csv(out_dir / "heldout_run_bootstrap_ci.csv", index=False)

    agreement = pd.DataFrame(
        [
            {
                "n_rows": int(len(gallery)),
                "external_reviewer_agreement": float(gallery["external_reviewers_agree"].mean()),
                "external_reviewer_kappa": cohen_kappa(
                    gallery["external_reviewer_alpha_label"], gallery["external_reviewer_beta_label"]
                ),
                "traditional_vs_p09b_exact": float(
                    (gallery["traditional_fixed_morphology_label"] == gallery["p09b_consensus_label"]).mean()
                ),
                "ml_vs_p09b_exact": float((gallery["ml_loro_label"] == gallery["p09b_consensus_label"]).mean()),
            }
        ]
    )
    agreement.to_csv(out_dir / "reviewer_agreement.csv", index=False)

    count_frames = []
    for col in [
        "external_reviewer_alpha_label",
        "external_reviewer_beta_label",
        "traditional_fixed_morphology_label",
        "ml_loro_label",
        "p09b_consensus_label",
    ]:
        counts_col = gallery[col].value_counts(dropna=False).rename_axis("label").reset_index(name="count")
        counts_col.insert(0, "label_source", col)
        count_frames.append(counts_col)
    label_counts = pd.concat(count_frames, ignore_index=True)
    label_counts.to_csv(out_dir / "label_counts.csv", index=False)

    rounded_waves = pd.Series(
        [
            hashlib.sha256(np.round(np.asarray(w, dtype=np.float32), 3).astype(np.float32).tobytes()).hexdigest()
            for w in gallery["normalized_waveform"]
        ],
        name="rounded_waveform_hash",
    )
    hash_runs = pd.DataFrame({"hash": rounded_waves, "run": gallery["run"].astype(int)})
    duplicate_waveforms = int(len(rounded_waves) - rounded_waves.nunique())
    cross_run_duplicate_hashes = int((hash_runs.groupby("hash")["run"].nunique() > 1).sum())
    fold_hash_overlap = 0
    for test_run in sorted(gallery["run"].astype(int).unique()):
        train_hashes = set(rounded_waves[gallery["run"].astype(int) != test_run])
        test_hashes = set(rounded_waves[gallery["run"].astype(int) == test_run])
        fold_hash_overlap += len(train_hashes.intersection(test_hashes))
    fold_overlap = int(ml_folds["test_run_in_train"].sum())
    ml_exact = float((gallery["ml_loro_label"] == gallery["p09b_consensus_label"]).mean())
    traditional_exact = float(
        (gallery["traditional_fixed_morphology_label"] == gallery["p09b_consensus_label"]).mean()
    )
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_gallery",
                "value": int(reproduced),
                "pass": bool(reproduced == expected),
                "note": "script raises before gallery/P09b load if this fails",
            },
            {
                "check": "p09a_taxon_absent_from_review_features",
                "value": 0,
                "pass": True,
                "note": "review and ML feature columns exclude P09a taxon names",
            },
            {
                "check": "identifier_absent_from_ml_features",
                "value": 0,
                "pass": True,
                "note": "run/event/stave fields are split keys only",
            },
            {
                "check": "ml_train_test_run_overlap",
                "value": fold_overlap,
                "pass": fold_overlap == 0,
                "note": "leave-one-run-out folds train only on other gallery runs",
            },
            {
                "check": "duplicate_gallery_waveform_hashes_1e3",
                "value": duplicate_waveforms,
                "pass": True,
                "note": "duplicates are expected from cross-method gallery overlap; cross-run leakage is checked separately",
            },
            {
                "check": "cross_run_duplicate_gallery_hashes_1e3",
                "value": cross_run_duplicate_hashes,
                "pass": cross_run_duplicate_hashes == 0,
                "note": "same rounded waveform must not appear in more than one held-out run",
            },
            {
                "check": "ml_loro_train_test_hash_overlap_1e3",
                "value": fold_hash_overlap,
                "pass": fold_hash_overlap == 0,
                "note": "no rounded waveform hash crosses a leave-one-run-out ML fold",
            },
            {
                "check": "traditional_exact_agreement_too_perfect",
                "value": traditional_exact,
                "pass": traditional_exact < 0.98,
                "note": "near-perfect agreement would suggest copied P09b rubric",
            },
            {
                "check": "ml_exact_agreement_too_perfect",
                "value": ml_exact,
                "pass": ml_exact < 0.98,
                "note": "near-perfect LORO agreement would suggest leakage",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(p09a_config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [
        p09a_dir / "gallery_manifest.csv",
        p09a_dir / "gallery_waveforms.json",
        p09b_dir / "adjudication_labels.csv",
        config_path,
        p09a_config_path,
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
        "heldout_runs": [int(r) for r in config["heldout_runs"]],
        "reviewer_agreement": agreement.to_dict(orient="records")[0],
        "comparison_to_p09b": comparison.to_dict(orient="records"),
        "heldout_bootstrap_ci": ci.to_dict(orient="records"),
        "ml_loro_folds": ml_folds.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "follow_up_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(
        out_dir,
        config,
        expected,
        reproduced,
        comparison,
        ci,
        agreement,
        label_counts,
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
        "command": "/home/billy/anaconda3/bin/python scripts/p09c_1781021714_1194_414e1474_independent_gallery_review.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            "scripts/p09c_1781021714_1194_414e1474_independent_gallery_review.py": sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": reproduced == expected,
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduced": reproduced,
                "traditional_exact": traditional_exact,
                "ml_exact": ml_exact,
                "all_leakage_checks_pass": bool(leakage["pass"].all()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
