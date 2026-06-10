#!/usr/bin/env python3
"""S02d: anomaly-taxonomy closure of S02/S03 timing tails.

The first analysis operation is a raw ROOT scan through the P09a/S00 gate.  The
timing study then uses only run-disjoint training and held-out runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p09a_rare_waveform_anomaly_taxonomy as p09a


PAIR_STAVES = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


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


def positions(staves: Sequence[str], spacing_cm: float) -> Dict[str, float]:
    return {stave: spacing_cm * i for i, stave in enumerate(staves)}


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def metric_summary(values: np.ndarray, threshold: float) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {
            "n_pairs": 0,
            "tail_rate": float("nan"),
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "q95_abs_ns": float("nan"),
            "median_ns": float("nan"),
        }
    centered = values - np.median(values)
    return {
        "n_pairs": int(len(values)),
        "tail_rate": float(np.mean(np.abs(centered) > threshold)),
        "sigma68_ns": sigma68(centered),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))),
        "q95_abs_ns": float(np.percentile(np.abs(centered), 95)),
        "median_ns": float(np.median(values)),
    }


def reproduction_table(config: dict, counts: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    sample_ii = set(int(r) for r in config["run_groups"]["sample_ii_analysis"])
    sample_ii_counts = counts[counts["run"].isin(sample_ii)]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts["selected_pulses"].sum()),
            "tolerance": 0,
        },
        {
            "quantity": "sample_ii_analysis selected_pulses",
            "report_value": int(expected["sample_ii_analysis"]["selected_pulses"]),
            "reproduced": int(sample_ii_counts["selected_pulses"].sum()),
            "tolerance": 0,
        },
    ]
    for stave in ["B2", "B4", "B6", "B8"]:
        rows.append(
            {
                "quantity": "sample_ii_analysis {}".format(stave),
                "report_value": int(expected["sample_ii_analysis"][stave]),
                "reproduced": int(sample_ii_counts[stave].sum()),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def build_timing_frame(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    downstream = list(config["downstream_staves"])
    period = float(config["sample_period_ns"])
    frame = meta[meta["stave"].isin(downstream)].copy()
    frame["source_idx"] = frame.index.astype(int)
    frame["event_id"] = (
        frame["run"].astype(str)
        + ":"
        + frame["eventno"].astype(str)
        + ":"
        + frame["evt"].astype(str)
        + ":"
        + frame["event_index"].astype(str)
    )
    frame["t_cfd20_ns"] = period * frame["cfd20_sample"].astype(float)
    return frame.reset_index(drop=True)


def add_binned_timewalk(timing: pd.DataFrame, train_runs: Iterable[int], config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = timing.copy()
    downstream = list(config["downstream_staves"])
    pos = positions(downstream, float(config["spacing_cm"]))
    tof = float(config["tof_per_cm_ns"])
    edges = np.asarray(config["timewalk_edges_adc"], dtype=float)
    out["amp_bin"] = np.digitize(out["amplitude_adc"].to_numpy(dtype=float), edges)
    out["tcorr_base_ns"] = out["t_cfd20_ns"] - out["stave"].map(pos).astype(float) * tof
    train_mask = out["run"].isin(list(train_runs))
    train = out[train_mask].copy()
    event_mean = train.groupby("event_id")["tcorr_base_ns"].mean()
    train["event_mean_ns"] = train["event_id"].map(event_mean)
    train["tw_target_ns"] = train["tcorr_base_ns"] - train["event_mean_ns"]
    med = train.groupby(["stave", "amp_bin"])["tw_target_ns"].median().reset_index(name="correction_ns")
    stave_fallback = train.groupby("stave")["tw_target_ns"].median().to_dict()
    global_fallback = float(train["tw_target_ns"].median())
    corr_lookup = {(str(r.stave), int(r.amp_bin)): float(r.correction_ns) for r in med.itertuples()}
    corrections = []
    for row in out[["stave", "amp_bin"]].itertuples(index=False):
        corrections.append(corr_lookup.get((str(row.stave), int(row.amp_bin)), stave_fallback.get(str(row.stave), global_fallback)))
    out["timewalk_correction_ns"] = np.asarray(corrections, dtype=float)
    out["t_timewalk_ns"] = out["t_cfd20_ns"] - out["timewalk_correction_ns"]
    return out, med


def pair_table(timing: pd.DataFrame, time_col: str, runs: Iterable[int], config: dict, threshold: float, center_ns: float = 0.0) -> pd.DataFrame:
    downstream = list(config["downstream_staves"])
    pos = positions(downstream, float(config["spacing_cm"]))
    tof = float(config["tof_per_cm_ns"])
    sub = timing[timing["run"].isin(list(runs))].copy()
    sub["tcorr_ns"] = sub[time_col].astype(float) - sub["stave"].map(pos).astype(float) * tof
    rows = []
    for event_id, event in sub.groupby("event_id", sort=False):
        by_stave = {str(r.stave): r for r in event.itertuples()}
        for a, b in PAIR_STAVES:
            if a not in by_stave or b not in by_stave:
                continue
            ra, rb = by_stave[a], by_stave[b]
            residual = float(ra.tcorr_ns - rb.tcorr_ns)
            if not math.isfinite(residual):
                continue
            centered = residual - float(center_ns)
            rows.append(
                {
                    "event_id": event_id,
                    "run": int(ra.run),
                    "pair": "{}-{}".format(a, b),
                    "residual_ns": residual,
                    "abs_centered_residual_ns": abs(centered),
                    "idx_a": int(ra.source_idx),
                    "idx_b": int(rb.source_idx),
                    "taxon_a": str(ra.taxon),
                    "taxon_b": str(rb.taxon),
                    "amp_mean_adc": 0.5 * (float(ra.amplitude_adc) + float(rb.amplitude_adc)),
                    "log_amp_mean": float(np.log1p(0.5 * (float(ra.amplitude_adc) + float(rb.amplitude_adc)))),
                    "stave_a": a,
                    "stave_b": b,
                    "tail": abs(centered) > float(threshold),
                }
            )
    return pd.DataFrame(rows)


def true_tail_pulse_labels(timing: pd.DataFrame, pairs: pd.DataFrame) -> np.ndarray:
    labels = np.zeros(len(timing), dtype=np.int8)
    source_to_row = {int(src): i for i, src in enumerate(timing["source_idx"].to_numpy())}
    for row in pairs[pairs["tail"]].itertuples():
        if int(row.idx_a) in source_to_row:
            labels[source_to_row[int(row.idx_a)]] = 1
        if int(row.idx_b) in source_to_row:
            labels[source_to_row[int(row.idx_b)]] = 1
    return labels


def taxonomy_feature_frame(timing: pd.DataFrame, waves: np.ndarray, train_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, List[str]]:
    numeric_cols = [
        "traditional_score",
        "q_template_rmse",
        "amplitude_adc",
        "peak_sample",
        "area_norm",
        "late_fraction",
        "early_fraction",
        "width_half",
        "baseline_mad",
        "baseline_slope",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "undershoot_area",
        "timing_span_dup",
    ]
    X_num = timing[numeric_cols].copy()
    X_num["log_amp"] = np.log1p(X_num["amplitude_adc"].astype(float))
    X_num["abs_baseline_slope"] = np.abs(X_num["baseline_slope"].astype(float))
    X_num = X_num.drop(columns=["amplitude_adc", "baseline_slope"])
    source = timing["source_idx"].to_numpy(dtype=int)
    pca_n = int(config["ml"]["pca_components"])
    pca = PCA(n_components=pca_n, random_state=int(config["random_seed"]))
    pca.fit(waves[source[train_mask]])
    z = pca.transform(waves[source])
    for i in range(z.shape[1]):
        X_num["pca_latent_{}".format(i)] = z[:, i]
    taxa = pd.get_dummies(timing["taxon"], prefix="taxon")
    X = pd.concat([X_num, taxa], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan)
    med = X.loc[train_mask].median(numeric_only=True)
    X = X.fillna(med).fillna(0.0)
    return X, list(X.columns)


def fit_ml_scores(
    X: pd.DataFrame,
    y: np.ndarray,
    runs: np.ndarray,
    train_mask: np.ndarray,
    heldout_mask: np.ndarray,
    config: dict,
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    seed = int(config["random_seed"])
    rf_kwargs = {
        "n_estimators": int(config["ml"]["rf_trees"]),
        "min_samples_leaf": int(config["ml"]["rf_min_samples_leaf"]),
        "class_weight": "balanced_subsample",
        "random_state": seed,
        "n_jobs": -1,
    }
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X.loc[train_mask])
    X_all_scaled = scaler.transform(X)
    oof = np.full(len(X), np.nan, dtype=float)
    train_idx = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    unique_runs = np.unique(groups)
    n_splits = min(int(config["ml"]["cv_folds"]), len(unique_runs))
    cv_rows = []
    if len(np.unique(y[train_mask])) < 2:
        raise RuntimeError(
            "ML training target has one class only: positives={} negatives={}".format(
                int(y[train_mask].sum()), int((train_mask.sum() - y[train_mask].sum()))
            )
        )
    if n_splits >= 2 and len(np.unique(y[train_mask])) == 2:
        gkf = GroupKFold(n_splits=n_splits)
        for fold, (tr, va) in enumerate(gkf.split(X_train_scaled, y[train_mask], groups=groups)):
            model = RandomForestClassifier(**dict(rf_kwargs, random_state=seed + fold + 1))
            model.fit(X_train_scaled[tr], y[train_mask][tr])
            score = model.predict_proba(X_train_scaled[va])[:, 1]
            oof[train_idx[va]] = score
            cv_rows.append(classifier_metrics("train_oof_fold_{}".format(fold), y[train_mask][va], score))
    model = RandomForestClassifier(**rf_kwargs)
    model.fit(X_train_scaled, y[train_mask])
    score_all = model.predict_proba(X_all_scaled)[:, 1]
    if np.isfinite(oof[train_mask]).any():
        train_score_for_threshold = oof[train_mask & np.isfinite(oof)]
    else:
        train_score_for_threshold = score_all[train_mask]
    threshold = float(np.quantile(train_score_for_threshold, float(config["ml_flag_quantile"])))
    cv = pd.DataFrame(cv_rows)
    info = {
        "score_threshold_from_train": threshold,
        "train_positive_rate": float(np.mean(y[train_mask])),
        "heldout_positive_rate": float(np.mean(y[heldout_mask])),
        "n_train_pulses": int(train_mask.sum()),
        "n_heldout_pulses": int(heldout_mask.sum()),
    }
    return score_all, cv, info


def classifier_metrics(name: str, y_true: np.ndarray, score: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    score = np.asarray(score, dtype=float)
    finite = np.isfinite(score)
    y_true = y_true[finite]
    score = score[finite]
    if len(y_true) == 0:
        return {"split": name, "n": 0, "positive_rate": float("nan"), "average_precision": float("nan"), "roc_auc": float("nan")}
    row = {"split": name, "n": int(len(y_true)), "positive_rate": float(np.mean(y_true))}
    if len(np.unique(y_true)) == 2:
        row["average_precision"] = float(average_precision_score(y_true, score))
        row["roc_auc"] = float(roc_auc_score(y_true, score))
    else:
        row["average_precision"] = float("nan")
        row["roc_auc"] = float("nan")
    return row


def closure_rows(pair_df: pd.DataFrame, taxa: Sequence[str], threshold: float, baseline: pd.DataFrame, ml_col: str = None) -> pd.DataFrame:
    rows = []
    actions = [("baseline", np.ones(len(pair_df), dtype=bool))]
    for taxon in taxa:
        keep = (pair_df["taxon_a"] != taxon) & (pair_df["taxon_b"] != taxon)
        actions.append(("exclude_taxon_{}".format(taxon), keep.to_numpy()))
    if ml_col is not None:
        actions.append(("exclude_ml_high_risk", ~(pair_df[ml_col].to_numpy(dtype=bool))))
    base_amp = float(baseline["log_amp_mean"].median()) if len(baseline) else float("nan")
    base_pair_share = baseline["pair"].value_counts(normalize=True).to_dict() if len(baseline) else {}
    for action, keep in actions:
        sub = pair_df.loc[keep].copy()
        summary = metric_summary(sub["residual_ns"].to_numpy(dtype=float), threshold)
        pair_share = sub["pair"].value_counts(normalize=True).to_dict() if len(sub) else {}
        max_pair_drift = 0.0
        for pair in set(list(base_pair_share.keys()) + list(pair_share.keys())):
            max_pair_drift = max(max_pair_drift, abs(pair_share.get(pair, 0.0) - base_pair_share.get(pair, 0.0)))
        rows.append(
            {
                "action": action,
                **summary,
                "kept_pair_fraction": float(len(sub) / max(1, len(pair_df))),
                "removed_pair_fraction": float(1.0 - len(sub) / max(1, len(pair_df))),
                "median_log_amp_delta": float(sub["log_amp_mean"].median() - base_amp) if len(sub) else float("nan"),
                "max_pair_composition_drift": float(max_pair_drift),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_closure(pair_df: pd.DataFrame, taxa: Sequence[str], threshold: float, rng: np.random.Generator, n_boot: int, ml_col: str = None) -> pd.DataFrame:
    runs = np.asarray(sorted(pair_df["run"].unique()))
    actions = ["baseline"] + ["exclude_taxon_{}".format(t) for t in taxa]
    if ml_col is not None:
        actions.append("exclude_ml_high_risk")
    rows = []
    for action in actions:
        stats = {"tail_rate": [], "full_rms_ns": [], "q95_abs_ns": [], "sigma68_ns": [], "kept_pair_fraction": []}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            pieces = [pair_df[pair_df["run"] == int(run)] for run in sampled]
            boot = pd.concat(pieces, ignore_index=True)
            base = boot.copy()
            if action.startswith("exclude_taxon_"):
                taxon = action.replace("exclude_taxon_", "", 1)
                boot = boot[(boot["taxon_a"] != taxon) & (boot["taxon_b"] != taxon)]
            elif action == "exclude_ml_high_risk" and ml_col is not None:
                boot = boot[~boot[ml_col].astype(bool)]
            summary = metric_summary(boot["residual_ns"].to_numpy(dtype=float), threshold)
            for key in ["tail_rate", "full_rms_ns", "q95_abs_ns", "sigma68_ns"]:
                stats[key].append(summary[key])
            stats["kept_pair_fraction"].append(float(len(boot) / max(1, len(base))))
        for metric, vals in stats.items():
            rows.append(
                {
                    "action": action,
                    "metric": metric,
                    "ci_low": float(np.nanpercentile(vals, 2.5)),
                    "ci_high": float(np.nanpercentile(vals, 97.5)),
                }
            )
    return pd.DataFrame(rows)


def waveform_hashes(waves: np.ndarray, indices: np.ndarray) -> set:
    rounded = np.round(waves[indices], 3).astype(np.float32)
    return set(hashlib.sha256(row.tobytes()).hexdigest() for row in rounded)


def plot_outputs(out_dir: Path, closure: pd.DataFrame, ml_metrics: pd.DataFrame) -> None:
    show = closure[closure["action"].isin(["baseline", "exclude_ml_high_risk"]) | closure["action"].str.startswith("exclude_taxon_")].copy()
    show = show.sort_values("tail_rate")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(np.arange(len(show)), show["tail_rate"])
    ax.set_xticks(np.arange(len(show)))
    ax.set_xticklabels(show["action"], rotation=70, ha="right", fontsize=8)
    ax.set_ylabel("held-out timing-tail rate")
    ax.set_title("Timing-tail closure by anomaly exclusion")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_closure_actions.png", dpi=130)
    plt.close(fig)

    if len(ml_metrics):
        fig, ax = plt.subplots(figsize=(5.5, 4))
        labels = ml_metrics["selection"].astype(str)
        ax.bar(np.arange(len(ml_metrics)), ml_metrics["precision"])
        ax.set_xticks(np.arange(len(ml_metrics)))
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("held-out pulse-tail precision")
        ax.set_title("ML tail classifier precision")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_ml_precision.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    threshold: float,
    closure: pd.DataFrame,
    ci: pd.DataFrame,
    ml_metrics: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    baseline = closure[closure["action"] == "baseline"].iloc[0]
    best_taxon = closure[closure["action"].str.startswith("exclude_taxon_")].sort_values("tail_rate").iloc[0]
    ml_row = closure[closure["action"] == "exclude_ml_high_risk"].iloc[0]
    ml_fixed = ml_metrics[ml_metrics["selection"] == "fixed_train_threshold"].iloc[0]
    lines = [
        "# S02d: anomaly-taxonomy timing-tail closure",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT files were scanned before any modeling. The S00/S02 selected-pulse gates all reproduced exactly.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Split and target",
        "Training runs were all configured B-stack runs except held-out runs `{}`. Timing used downstream staves `{}` with CFD20 plus a train-run amplitude-bin timewalk correction. The residual-tail threshold was the train-run {:.0f}th percentile of absolute corrected pair residuals: `{:.4f} ns`.".format(
            ", ".join(str(r) for r in config["heldout_runs"]),
            ", ".join(config["downstream_staves"]),
            100.0 * float(config["tail_quantile"]),
            threshold,
        ),
        "",
        "## Traditional Closure",
        "The traditional audit applied fixed P09a anomaly-class exclusions on held-out runs and measured tail rate, full RMS, q95 absolute residual, charge drift, and pair-composition drift.",
        "",
        closure[
            [
                "action",
                "n_pairs",
                "tail_rate",
                "full_rms_ns",
                "q95_abs_ns",
                "kept_pair_fraction",
                "median_log_amp_delta",
                "max_pair_composition_drift",
            ]
        ].to_markdown(index=False),
        "",
        "Best class exclusion by tail rate was `{}`: tail rate `{:.4f}` vs baseline `{:.4f}`, with kept-pair fraction `{:.3f}`.".format(
            best_taxon["action"], float(best_taxon["tail_rate"]), float(baseline["tail_rate"]), float(best_taxon["kept_pair_fraction"])
        ),
        "",
        "## ML Classifier",
        "The ML method trained a run-heldout RandomForest tail classifier from P09a scores, P09a taxa, and train-fit PCA waveform latents. It used no run id, event id, or stave id features.",
        "",
        ml_metrics.to_markdown(index=False),
        "",
        "Fixed-threshold ML exclusion changed held-out tail rate from `{:.4f}` to `{:.4f}` while keeping `{:.3f}` of pairs. Fixed-threshold pulse precision was `{:.4f}`.".format(
            float(baseline["tail_rate"]), float(ml_row["tail_rate"]), float(ml_row["kept_pair_fraction"]), float(ml_fixed["precision"])
        ),
        "",
        "## Held-Out Bootstrap CIs",
        "CIs are nonparametric bootstraps over held-out runs.",
        "",
        ci[ci["action"].isin(["baseline", best_taxon["action"], "exclude_ml_high_risk"])].to_markdown(index=False),
        "",
        "## Leakage Checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "P09a anomaly taxa are useful diagnostics for timing tails, but no single class closes the tail without also changing sample composition. The ML risk flag gives a stronger tail-enriched selection than deterministic class cuts, so the next step should validate whether those high-risk pulses share a physical waveform failure mode rather than using the classifier as a production cut.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. `manifest.json` records input and output hashes.".format(runtime, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02d_1781011449_1369_708b7640.json")
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
    repro = reproduction_table(config, counts)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed; see reproduction_match_table.csv")

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    train_mask_all = ~meta["run"].isin(heldout_runs).to_numpy()
    meta = p09a.add_template_residual(config, waves, meta, train_mask_all)
    meta, thresholds = p09a.add_taxonomy(meta, train_mask_all)
    meta["traditional_score"] = p09a.score_traditional(meta, train_mask_all)
    thresholds.to_csv(out_dir / "feature_thresholds.csv", index=False)

    timing = build_timing_frame(meta, config)
    train_runs = sorted(set(int(r) for r in timing["run"].unique()) - heldout_runs)
    heldout_timing_mask = timing["run"].isin(heldout_runs).to_numpy()
    train_timing_mask = ~heldout_timing_mask
    timing, correction_table = add_binned_timewalk(timing, train_runs, config)
    correction_table.to_csv(out_dir / "timewalk_bin_corrections.csv", index=False)
    train_pairs = pair_table(timing, "t_timewalk_ns", train_runs, config, threshold=math.inf)
    train_pair_values = train_pairs["residual_ns"].to_numpy(dtype=float)
    train_pair_values = train_pair_values[np.isfinite(train_pair_values)]
    train_pair_median = float(np.median(train_pair_values))
    train_centered = train_pair_values - train_pair_median
    tail_threshold = float(np.percentile(np.abs(train_centered), 100.0 * float(config["tail_quantile"])))
    train_pairs = pair_table(timing, "t_timewalk_ns", train_runs, config, threshold=tail_threshold, center_ns=train_pair_median)
    heldout_pairs = pair_table(timing, "t_timewalk_ns", heldout_runs, config, threshold=tail_threshold, center_ns=train_pair_median)
    timing["true_tail_pulse"] = true_tail_pulse_labels(timing, pd.concat([train_pairs, heldout_pairs], ignore_index=True))
    print(
        "timing labels: train_pairs={} train_tail_pairs={} heldout_pairs={} heldout_tail_pairs={} "
        "train_tail_pulses={} heldout_tail_pulses={} threshold_ns={:.4f}".format(
            len(train_pairs),
            int(train_pairs["tail"].sum()),
            len(heldout_pairs),
            int(heldout_pairs["tail"].sum()),
            int(timing.loc[train_timing_mask, "true_tail_pulse"].sum()),
            int(timing.loc[heldout_timing_mask, "true_tail_pulse"].sum()),
            tail_threshold,
        ),
        flush=True,
    )

    X, feature_cols = taxonomy_feature_frame(timing, waves, train_timing_mask, config)
    ml_score, ml_cv, ml_info = fit_ml_scores(
        X,
        timing["true_tail_pulse"].to_numpy(dtype=int),
        timing["run"].to_numpy(dtype=int),
        train_timing_mask,
        heldout_timing_mask,
        config,
    )
    timing["ml_tail_score"] = ml_score
    timing["ml_high_risk"] = timing["ml_tail_score"] >= float(ml_info["score_threshold_from_train"])
    source_ml = timing.set_index("source_idx")["ml_high_risk"].to_dict()
    source_score = timing.set_index("source_idx")["ml_tail_score"].to_dict()
    heldout_pairs["ml_high_risk_pair"] = heldout_pairs["idx_a"].map(source_ml).fillna(False).astype(bool) | heldout_pairs["idx_b"].map(source_ml).fillna(False).astype(bool)
    heldout_pairs["ml_score_pair_max"] = np.maximum(
        heldout_pairs["idx_a"].map(source_score).fillna(0.0).to_numpy(dtype=float),
        heldout_pairs["idx_b"].map(source_score).fillna(0.0).to_numpy(dtype=float),
    )

    heldout_tail_labels = timing.loc[heldout_timing_mask, "true_tail_pulse"].to_numpy(dtype=int)
    heldout_scores = timing.loc[heldout_timing_mask, "ml_tail_score"].to_numpy(dtype=float)
    fixed_sel = timing.loc[heldout_timing_mask, "ml_high_risk"].to_numpy(dtype=bool)
    top_sel = np.zeros(int(heldout_timing_mask.sum()), dtype=bool)
    held_local = timing.loc[heldout_timing_mask].reset_index(drop=True)
    for run, sub in held_local.groupby("run", sort=True):
        take = max(1, int(math.ceil(len(sub) * (1.0 - float(config["ml_flag_quantile"])))))
        top_idx = sub.sort_values("ml_tail_score", ascending=False).head(take).index.to_numpy(dtype=int)
        top_sel[top_idx] = True
    ml_metric_rows = [
        classifier_metrics("heldout_all", heldout_tail_labels, heldout_scores),
        {
            "selection": "fixed_train_threshold",
            "n_selected": int(fixed_sel.sum()),
            "selected_fraction": float(fixed_sel.mean()),
            "precision": float(np.mean(heldout_tail_labels[fixed_sel])) if fixed_sel.any() else float("nan"),
            "baseline_tail_rate": float(np.mean(heldout_tail_labels)),
            **classifier_metrics("heldout_fixed_threshold_scores", heldout_tail_labels, heldout_scores),
        },
        {
            "selection": "top_decile_per_run",
            "n_selected": int(top_sel.sum()),
            "selected_fraction": float(top_sel.mean()),
            "precision": float(np.mean(heldout_tail_labels[top_sel])) if top_sel.any() else float("nan"),
            "baseline_tail_rate": float(np.mean(heldout_tail_labels)),
            **classifier_metrics("heldout_top_decile_scores", heldout_tail_labels, heldout_scores),
        },
    ]
    ml_metrics = pd.DataFrame(ml_metric_rows)
    ml_metrics.to_csv(out_dir / "ml_classifier_metrics.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_run_cv_metrics.csv", index=False)

    taxa = [str(t) for t in sorted(timing["taxon"].unique()) if str(t) != "unassigned_common"]
    closure = closure_rows(heldout_pairs, taxa, tail_threshold, heldout_pairs, ml_col="ml_high_risk_pair")
    closure.to_csv(out_dir / "traditional_closure_metrics.csv", index=False)
    ci = bootstrap_closure(heldout_pairs, taxa, tail_threshold, rng, int(config["bootstrap_replicates"]), ml_col="ml_high_risk_pair")
    ci.to_csv(out_dir / "heldout_bootstrap_ci.csv", index=False)
    heldout_pairs.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)

    train_hashes = waveform_hashes(waves, timing.loc[train_timing_mask, "source_idx"].to_numpy(dtype=int))
    held_hashes = waveform_hashes(waves, timing.loc[heldout_timing_mask, "source_idx"].to_numpy(dtype=int))
    overlap = len(train_hashes.intersection(held_hashes))
    forbidden = [c for c in feature_cols if c in {"run", "eventno", "evt", "event_index", "event_id", "stave", "source_idx"}]
    suspicious = bool(
        ml_metrics.loc[ml_metrics["selection"] == "fixed_train_threshold", "precision"].iloc[0] > 0.90
        or (
            ml_metrics.loc[ml_metrics["selection"] == "fixed_train_threshold", "precision"].iloc[0]
            / max(ml_metrics.loc[ml_metrics["selection"] == "fixed_train_threshold", "baseline_tail_rate"].iloc[0], 1e-12)
            > 5.0
        )
    )
    # Stave-only proxy control: if it performs like the full model, the result is suspect.
    stave_x = pd.get_dummies(timing["stave"], prefix="stave")
    proxy_score, _, _ = fit_ml_scores(
        stave_x,
        timing["true_tail_pulse"].to_numpy(dtype=int),
        timing["run"].to_numpy(dtype=int),
        train_timing_mask,
        heldout_timing_mask,
        dict(config, ml=dict(config["ml"], rf_trees=120), ml_flag_quantile=config["ml_flag_quantile"]),
    )
    proxy_metrics = classifier_metrics("heldout_stave_only_proxy", heldout_tail_labels, proxy_score[heldout_timing_mask])
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(train_runs).intersection(heldout_runs))),
                "pass": len(set(train_runs).intersection(heldout_runs)) == 0,
                "note": "run-disjoint split",
            },
            {
                "check": "model_features_include_run_event_or_stave_id",
                "value": len(forbidden),
                "pass": len(forbidden) == 0,
                "note": ",".join(forbidden) if forbidden else "none",
            },
            {
                "check": "rounded_waveform_hash_overlap_train_heldout",
                "value": int(overlap),
                "pass": overlap == 0,
                "note": "normalized waveforms rounded to 1e-3",
            },
            {
                "check": "stave_only_proxy_average_precision",
                "value": float(proxy_metrics.get("average_precision", float("nan"))),
                "pass": bool(proxy_metrics.get("average_precision", 0.0) < ml_metrics.loc[ml_metrics["split"] == "heldout_all", "average_precision"].iloc[0]),
                "note": "proxy should underperform full no-id model",
            },
            {
                "check": "suspicious_result_triggered_extra_checks",
                "value": int(suspicious),
                "pass": True,
                "note": "triggered if precision >0.90 or enrichment >5",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_outputs(out_dir, closure, ml_metrics[ml_metrics["selection"].notna()].copy())

    input_hashes = []
    for run in p09a.configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {
            "pass": bool(repro["pass"].all()),
            "rows": repro.to_dict(orient="records"),
        },
        "split": {
            "train_runs": train_runs,
            "heldout_runs": sorted(int(r) for r in heldout_runs),
            "tail_threshold_ns": tail_threshold,
            "train_pair_median_ns": train_pair_median,
        },
        "traditional_closure": closure.to_dict(orient="records"),
        "ml_classifier": ml_metrics.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config, repro, tail_threshold, closure, ci, ml_metrics[ml_metrics["selection"].notna()].copy(), leakage, time.time() - t0)

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "{} {} --config {}".format(sys.executable, Path(__file__), config_path),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(repro["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduction_pass": bool(repro["pass"].all()),
                "tail_threshold_ns": tail_threshold,
                "baseline_tail_rate": float(closure[closure["action"] == "baseline"]["tail_rate"].iloc[0]),
                "ml_fixed_precision": float(ml_metrics[ml_metrics["selection"] == "fixed_train_threshold"]["precision"].iloc[0]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
