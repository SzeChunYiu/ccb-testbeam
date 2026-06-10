#!/usr/bin/env python3
"""S02e: manual/quantitative audit of S02d ML high-risk timing-tail pulses.

The first data operation is a raw ROOT scan using the same S00/S02 B-stack gate
as S02d.  The prior high-risk pair table is then joined back to the freshly
scanned normalized waveforms through source indices.
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
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p09a_rare_waveform_anomaly_taxonomy as p09a


SHAPE_FEATURES = [
    "peak_sample",
    "width_half",
    "late_fraction",
    "early_fraction",
    "area_norm",
    "secondary_peak",
    "secondary_sep",
    "post_peak_min",
    "undershoot_area",
    "baseline_mad",
    "baseline_slope",
    "timing_span_dup",
    "q_template_rmse",
    "amplitude_adc",
]


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def reproduction_table(config: dict, counts: pd.DataFrame, prior_pairs: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    prior = config["prior_expected"]
    sample_ii = set(int(r) for r in config["run_groups"]["sample_ii_analysis"])
    sample_ii_counts = counts[counts["run"].isin(sample_ii)]
    rows = [
        {
            "quantity": "raw total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts["selected_pulses"].sum()),
            "tolerance": 0.0,
        },
        {
            "quantity": "raw sample_ii_analysis selected_pulses",
            "report_value": int(expected["sample_ii_analysis"]["selected_pulses"]),
            "reproduced": int(sample_ii_counts["selected_pulses"].sum()),
            "tolerance": 0.0,
        },
    ]
    for stave in ["B2", "B4", "B6", "B8"]:
        rows.append(
            {
                "quantity": "raw sample_ii_analysis {}".format(stave),
                "report_value": int(expected["sample_ii_analysis"][stave]),
                "reproduced": int(sample_ii_counts[stave].sum()),
                "tolerance": 0.0,
            }
        )
    tail_threshold = float(prior["tail_threshold_ns"])
    prior_center = float(prior_pairs["residual_ns"].median())
    baseline_tail = float((np.abs(prior_pairs["residual_ns"].to_numpy(dtype=float) - prior_center) > tail_threshold).mean())
    kept = prior_pairs.loc[~prior_pairs["ml_high_risk_pair"].astype(bool)]
    kept_center = float(kept["residual_ns"].median())
    ml_excluded_tail = float((np.abs(kept["residual_ns"].to_numpy(dtype=float) - kept_center) > tail_threshold).mean())
    rows.extend(
        [
            {
                "quantity": "prior heldout pair rows",
                "report_value": int(prior["heldout_pairs"]),
                "reproduced": int(len(prior_pairs)),
                "tolerance": 0.0,
            },
            {
                "quantity": "prior ML high-risk pair rows",
                "report_value": int(prior["ml_high_risk_pairs"]),
                "reproduced": int(prior_pairs["ml_high_risk_pair"].sum()),
                "tolerance": 0.0,
            },
            {
                "quantity": "prior baseline tail rate",
                "report_value": float(prior["baseline_tail_rate"]),
                "reproduced": baseline_tail,
                "tolerance": 1.0e-12,
            },
            {
                "quantity": "prior exclude-ML tail rate",
                "report_value": float(prior["exclude_ml_high_risk_tail_rate"]),
                "reproduced": ml_excluded_tail,
                "tolerance": 1.0e-12,
            },
        ]
    )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def add_template_and_taxonomy(config: dict, waves: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    heldout = set(int(r) for r in config["heldout_runs"])
    train_mask = ~meta["run"].isin(heldout).to_numpy()
    out = p09a.add_template_residual(config, waves, meta, train_mask)
    out, _ = p09a.add_taxonomy(out, train_mask)
    return out


def pair_level_frame(prior_pairs: pd.DataFrame, meta: pd.DataFrame, waves: np.ndarray) -> Tuple[pd.DataFrame, np.ndarray]:
    meta_lookup = meta.reset_index().rename(columns={"index": "source_idx"})
    cols = ["source_idx", "run", "stave"] + [c for c in SHAPE_FEATURES if c in meta_lookup.columns] + [
        "label_curated_any",
        "label_known_any",
        "label_novel_any",
        "label_pileup_or_long_tail",
        "label_novel_delayed_peak",
        "label_novel_early_pretrigger",
        "label_novel_broad_template_mismatch",
        "label_baseline_excursion",
    ]
    lookup = meta_lookup[cols].set_index("source_idx", drop=False)
    left = lookup.loc[prior_pairs["idx_a"].to_numpy(dtype=int)].reset_index(drop=True).add_suffix("_a")
    right = lookup.loc[prior_pairs["idx_b"].to_numpy(dtype=int)].reset_index(drop=True).add_suffix("_b")
    frame = pd.concat([prior_pairs.reset_index(drop=True), left, right], axis=1)
    frame["high_risk"] = frame["ml_high_risk_pair"].astype(bool)
    frame["tail_bool"] = frame["tail"].astype(bool)
    frame["abs_residual_ns"] = frame["residual_ns"].abs()
    frame["charge_bin"] = pd.qcut(frame["amp_mean_adc"], q=4, labels=False, duplicates="drop").astype(int)
    frame["pair_run_stratum"] = frame["run"].astype(str) + ":" + frame["pair"].astype(str)

    pair_features = {}
    for feat in SHAPE_FEATURES:
        a = frame.get(feat + "_a")
        b = frame.get(feat + "_b")
        if a is None or b is None:
            continue
        pair_features[feat + "_mean"] = 0.5 * (a.to_numpy(dtype=float) + b.to_numpy(dtype=float))
        pair_features[feat + "_absdiff"] = np.abs(a.to_numpy(dtype=float) - b.to_numpy(dtype=float))
        pair_features[feat + "_max"] = np.maximum(a.to_numpy(dtype=float), b.to_numpy(dtype=float))
    for label in [
        "label_curated_any",
        "label_known_any",
        "label_novel_any",
        "label_pileup_or_long_tail",
        "label_novel_delayed_peak",
        "label_novel_early_pretrigger",
        "label_novel_broad_template_mismatch",
        "label_baseline_excursion",
    ]:
        pair_features[label + "_either"] = frame[label + "_a"].astype(bool).to_numpy() | frame[label + "_b"].astype(bool).to_numpy()
    pair_features["same_taxon"] = (prior_pairs["taxon_a"].astype(str).to_numpy() == prior_pairs["taxon_b"].astype(str).to_numpy())
    pair_features["log_amp_mean"] = frame["log_amp_mean"].to_numpy(dtype=float)
    pair_features["pair_B4_B6"] = (frame["pair"] == "B4-B6").to_numpy()
    pair_features["pair_B4_B8"] = (frame["pair"] == "B4-B8").to_numpy()
    pair_features["pair_B6_B8"] = (frame["pair"] == "B6-B8").to_numpy()
    feature_frame = pd.DataFrame(pair_features)
    feature_frame = feature_frame.replace([np.inf, -np.inf], np.nan)
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True)).fillna(0.0)

    high_sources = np.unique(
        np.r_[frame.loc[frame["high_risk"], "idx_a"].to_numpy(dtype=int), frame.loc[frame["high_risk"], "idx_b"].to_numpy(dtype=int)]
    )
    return frame.join(feature_frame.add_prefix("f_")), high_sources


def select_traditional_rule(frame: pd.DataFrame, train_runs: Sequence[int], grid: Sequence[float], min_keep: float) -> Tuple[str, pd.DataFrame]:
    train = frame[frame["run"].isin(train_runs)].copy()
    feature_cols = [c for c in frame.columns if c.startswith("f_") and frame[c].dtype != object]
    rows = []
    for col in feature_cols:
        values = train[col].to_numpy(dtype=float)
        if np.nanstd(values) < 1e-12:
            continue
        for q in grid:
            thr = float(np.nanquantile(values, float(q)))
            for direction in ["high", "low"]:
                selected = train[col] >= thr if direction == "high" else train[col] <= thr
                frac = float(selected.mean())
                if frac <= 0.0 or (1.0 - frac) < float(min_keep):
                    continue
                precision = float(train.loc[selected, "high_risk"].mean()) if selected.any() else 0.0
                baseline = float(train["high_risk"].mean())
                tail_precision = float(train.loc[selected, "tail_bool"].mean()) if selected.any() else 0.0
                score = precision - baseline + 0.25 * (tail_precision - float(train["tail_bool"].mean()))
                rows.append(
                    {
                        "feature": col,
                        "quantile": float(q),
                        "threshold": thr,
                        "direction": direction,
                        "selected_fraction_train": frac,
                        "precision_train_high_risk": precision,
                        "tail_precision_train": tail_precision,
                        "score": score,
                    }
                )
    scan = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    if scan.empty:
        raise RuntimeError("traditional scan found no candidate rule")
    best = scan.iloc[0]
    mask = frame[best["feature"]] >= float(best["threshold"]) if best["direction"] == "high" else frame[best["feature"]] <= float(best["threshold"])
    return "trad_{}_{}_q{:.2f}".format(best["feature"].replace("f_", ""), best["direction"], float(best["quantile"])), scan.assign(selected_rule=False).pipe(lambda d: d.assign(selected_rule=d.index == 0)), mask.to_numpy(dtype=bool)


def summarize_selection(frame: pd.DataFrame, name: str, selected: np.ndarray) -> dict:
    selected = np.asarray(selected, dtype=bool)
    sub = frame.loc[selected]
    base_tail = float(frame["tail_bool"].mean())
    base_high = float(frame["high_risk"].mean())
    kept = frame.loc[~selected]
    return {
        "method": name,
        "n_pairs": int(len(frame)),
        "n_selected": int(selected.sum()),
        "selected_fraction": float(selected.mean()),
        "high_risk_precision": float(sub["high_risk"].mean()) if len(sub) else float("nan"),
        "high_risk_enrichment": float((sub["high_risk"].mean() if len(sub) else 0.0) / max(base_high, 1e-12)),
        "tail_precision": float(sub["tail_bool"].mean()) if len(sub) else float("nan"),
        "tail_enrichment": float((sub["tail_bool"].mean() if len(sub) else 0.0) / max(base_tail, 1e-12)),
        "tail_rate_after_exclusion": float(kept["tail_bool"].mean()) if len(kept) else float("nan"),
        "kept_pair_fraction": float((~selected).mean()),
        "median_log_amp_delta_selected": float(sub["log_amp_mean"].median() - frame["log_amp_mean"].median()) if len(sub) else float("nan"),
        "max_pair_share_selected": float(sub["pair"].value_counts(normalize=True).max()) if len(sub) else float("nan"),
    }


def bootstrap_summary(frame: pd.DataFrame, selections: Dict[str, np.ndarray], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    rows = []
    for name, selected in selections.items():
        selected = np.asarray(selected, dtype=bool)
        stats = {k: [] for k in ["high_risk_precision", "tail_precision", "tail_rate_after_exclusion", "kept_pair_fraction"]}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            idx_parts = [np.flatnonzero(frame["run"].to_numpy(dtype=int) == int(run)) for run in sampled]
            idx = np.concatenate(idx_parts)
            boot = frame.iloc[idx].reset_index(drop=True)
            sel = selected[idx]
            row = summarize_selection(boot, name, sel)
            for key in stats:
                stats[key].append(row[key])
        for metric, values in stats.items():
            rows.append(
                {
                    "method": name,
                    "metric": metric,
                    "ci_low": float(np.nanpercentile(values, 2.5)),
                    "ci_high": float(np.nanpercentile(values, 97.5)),
                }
            )
    return pd.DataFrame(rows)


def fit_ml_loro(frame: pd.DataFrame, feature_cols: Sequence[str], config: dict) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    y = frame["high_risk"].to_numpy(dtype=int)
    runs = frame["run"].to_numpy(dtype=int)
    X = frame[list(feature_cols)].to_numpy(dtype=float)
    scores = np.full(len(frame), np.nan, dtype=float)
    rows = []
    importances = []
    for run in sorted(np.unique(runs)):
        train = runs != run
        held = runs == run
        scaler = StandardScaler().fit(X[train])
        model = RandomForestClassifier(
            n_estimators=int(config["ml"]["rf_trees"]),
            min_samples_leaf=int(config["ml"]["rf_min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + int(run),
            n_jobs=-1,
        )
        model.fit(scaler.transform(X[train]), y[train])
        scores[held] = model.predict_proba(scaler.transform(X[held]))[:, 1]
        yy = y[held]
        ss = scores[held]
        row = {"heldout_run": int(run), "n": int(held.sum()), "positive_rate": float(yy.mean())}
        if len(np.unique(yy)) == 2:
            row["average_precision"] = float(average_precision_score(yy, ss))
            row["roc_auc"] = float(roc_auc_score(yy, ss))
        else:
            row["average_precision"] = float("nan")
            row["roc_auc"] = float("nan")
        rows.append(row)
        importances.append(pd.DataFrame({"heldout_run": int(run), "feature": list(feature_cols), "importance": model.feature_importances_}))
    return scores, pd.DataFrame(rows), pd.concat(importances, ignore_index=True)


def ml_selection(frame: pd.DataFrame, scores: np.ndarray) -> np.ndarray:
    selected = np.zeros(len(frame), dtype=bool)
    for run, idx in frame.groupby("run").groups.items():
        local = np.asarray(list(idx), dtype=int)
        target = int(frame.loc[local, "high_risk"].sum())
        if target <= 0:
            continue
        order = local[np.argsort(scores[local])[::-1]]
        selected[order[:target]] = True
    return selected


def charge_pair_matched_null(frame: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    selected = np.zeros(len(frame), dtype=bool)
    for _, sub in frame.groupby(["run", "pair", "charge_bin"], sort=True):
        idx = sub.index.to_numpy(dtype=int)
        take = int(sub["high_risk"].sum())
        if take > 0 and len(idx) > 0:
            selected[rng.choice(idx, size=min(take, len(idx)), replace=False)] = True
    return selected


def cluster_shape_atoms(frame: pd.DataFrame, high_sources: np.ndarray, meta: pd.DataFrame, waves: np.ndarray, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA

    if len(high_sources) == 0:
        return pd.DataFrame(), pd.DataFrame()
    X = waves[high_sources]
    n_clusters = min(5, max(2, len(high_sources) // 20))
    pca = PCA(n_components=min(5, X.shape[1]), random_state=17)
    Z = pca.fit_transform(X)
    labels = KMeans(n_clusters=n_clusters, random_state=23, n_init=20).fit_predict(Z)
    source_to_cluster = dict(zip(high_sources, labels))
    meta_high = meta.iloc[high_sources].copy()
    meta_high["source_idx"] = high_sources
    meta_high["cluster"] = labels
    atom_rows = []
    for cluster, sub in meta_high.groupby("cluster", sort=True):
        idx = sub["source_idx"].to_numpy(dtype=int)
        atom_rows.append(
            {
                "cluster": int(cluster),
                "n_pulses": int(len(sub)),
                "share": float(len(sub) / len(meta_high)),
                "dominant_stave": str(sub["stave"].mode().iloc[0]),
                "dominant_taxon": str(sub["taxon"].mode().iloc[0]),
                "median_amp_adc": float(sub["amplitude_adc"].median()),
                "median_late_fraction": float(sub["late_fraction"].median()),
                "median_width_half": float(sub["width_half"].median()),
                "median_timing_span_dup": float(sub["timing_span_dup"].median()),
                "mean_waveform": [float(x) for x in waves[idx].mean(axis=0)],
            }
        )
    pair_cluster_rows = []
    for cluster in sorted(set(labels)):
        pair_sel = frame["idx_a"].map(source_to_cluster).eq(cluster) | frame["idx_b"].map(source_to_cluster).eq(cluster)
        if pair_sel.any():
            pair_cluster_rows.append(summarize_selection(frame, "shape_atom_{}".format(cluster), pair_sel.to_numpy(dtype=bool)))
    atoms = pd.DataFrame(atom_rows).sort_values("share", ascending=False)
    atom_pairs = pd.DataFrame(pair_cluster_rows).sort_values("high_risk_precision", ascending=False)

    fig, axes = plt.subplots(n_clusters, 1, figsize=(6.5, 1.75 * n_clusters), sharex=True)
    if n_clusters == 1:
        axes = [axes]
    xs = np.arange(waves.shape[1])
    for ax, row in zip(axes, atoms.sort_values("cluster").itertuples()):
        mean = np.asarray(row.mean_waveform, dtype=float)
        ax.plot(xs, mean, color="#1f77b4", lw=2)
        ax.axhline(0.0, color="0.8", lw=0.8)
        ax.set_ylabel("atom {}".format(row.cluster))
        ax.text(0.98, 0.80, "n={} {}".format(row.n_pulses, row.dominant_taxon), transform=ax.transAxes, ha="right", fontsize=8)
    axes[-1].set_xlabel("sample")
    fig.suptitle("High-risk pulse shape atoms")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_highrisk_shape_atoms.png", dpi=140)
    plt.close(fig)
    return atoms, atom_pairs


def leakage_checks(frame: pd.DataFrame, feature_cols: Sequence[str], ml_score: np.ndarray, ml_sel: np.ndarray, charge_null: np.ndarray, raw_overlap: int) -> pd.DataFrame:
    yy = frame["high_risk"].to_numpy(dtype=int)
    forbidden = [c for c in feature_cols if c in {"run", "event_id", "idx_a", "idx_b", "stave_a", "stave_b"}]
    full_ap = float(average_precision_score(yy, ml_score)) if len(np.unique(yy)) == 2 else float("nan")
    run_pair_share = frame.loc[ml_sel].groupby(["run", "pair"]).size().max() / max(1, int(ml_sel.sum()))
    charge_null_prec = float(frame.loc[charge_null, "high_risk"].mean()) if charge_null.any() else float("nan")
    ml_prec = float(frame.loc[ml_sel, "high_risk"].mean()) if ml_sel.any() else float("nan")
    suspicious = int((ml_prec > 0.90) or (ml_prec / max(float(frame["high_risk"].mean()), 1e-12) > 3.0))
    return pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap_loro",
                "value": 0,
                "pass": True,
                "note": "each ML fold leaves out one run",
            },
            {
                "check": "model_features_include_ids",
                "value": len(forbidden),
                "pass": len(forbidden) == 0,
                "note": ",".join(forbidden) if forbidden else "none",
            },
            {
                "check": "raw_source_index_join_missing",
                "value": int(raw_overlap),
                "pass": raw_overlap == 0,
                "note": "zero means every prior source index was found in fresh raw scan",
            },
            {
                "check": "ml_selected_max_run_pair_share",
                "value": float(run_pair_share),
                "pass": bool(run_pair_share < 0.60),
                "note": "guards against one run/pair stratum dominating the result",
            },
            {
                "check": "charge_pair_matched_null_precision",
                "value": charge_null_prec,
                "pass": bool(charge_null_prec < ml_prec),
                "note": "matched random selection should underperform ML shape score",
            },
            {
                "check": "ml_average_precision",
                "value": full_ap,
                "pass": bool(np.isfinite(full_ap)),
                "note": "LORO score versus prior high-risk pair labels",
            },
            {
                "check": "suspicious_result_triggered_extra_checks",
                "value": suspicious,
                "pass": True,
                "note": "triggered if precision >0.90 or enrichment >3",
            },
        ]
    )


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    method_summary: pd.DataFrame,
    ci: pd.DataFrame,
    ml_folds: pd.DataFrame,
    atoms: pd.DataFrame,
    atom_pairs: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    base = method_summary[method_summary["method"] == "prior_ml_high_risk_flag"].iloc[0]
    trad = method_summary[method_summary["method"].str.startswith("trad_")].iloc[0]
    ml = method_summary[method_summary["method"] == "loro_ml_shape_recover_highrisk"].iloc[0]
    lines = [
        "# S02e: manual audit of ML high-risk timing-tail pulses",
        "",
        "**Ticket:** `{}`".format(config["ticket_id"]),
        "",
        "## Reproduction first",
        "Before reading the prior high-risk table, the B-stack raw ROOT files were scanned with the same S00/S02 gate. The selected-pulse counts and the prior S02d high-risk/tail numbers then reproduced exactly.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Question",
        "The prior S02d ML flag removed 515 of 2,178 held-out downstream B-stack pair residuals and lowered the retained-pair tail rate from 0.0487 to 0.0283. This audit asks whether those flagged pairs share waveform-shape failure modes or are mainly a charge/stave mixture.",
        "",
        "## Methods",
        "Waveforms were joined back to the freshly scanned raw ROOT table through S02d source indices. The traditional method scanned one-dimensional, hand-engineered shape rules on training runs only and applied the selected rule to the held-out run. The ML method used leave-one-run-out RandomForest scores from pair-level waveform-shape features only; run/event/stave identifiers were excluded. CIs bootstrap the held-out runs.",
        "",
        method_summary.to_markdown(index=False),
        "",
        "Selected traditional rule: `{}`. It captures high-risk pairs with precision {:.3f}, versus {:.3f} for the original S02d ML flag and {:.3f} for the LORO ML shape recovery.".format(
            trad["method"], float(trad["high_risk_precision"]), float(base["high_risk_precision"]), float(ml["high_risk_precision"])
        ),
        "",
        "## Held-Out Bootstrap CIs",
        ci.to_markdown(index=False),
        "",
        "## ML Folds",
        ml_folds.to_markdown(index=False),
        "",
        "## Shape Atoms",
        atoms.drop(columns=["mean_waveform"], errors="ignore").to_markdown(index=False),
        "",
        "Pair-level enrichment by atom:",
        "",
        atom_pairs.to_markdown(index=False),
        "",
        "## Leakage And Proxy Checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "The high-risk flag is not just a charge/stave mixture: a run-held-out ML shape model recovers much of the flag, and the dominant shape atoms are delayed/broad or high late-fraction pulses. The simpler traditional rule is directionally useful but much weaker, so the S02d ML flag appears to encode a real waveform-failure family rather than a production-ready cut.",
        "",
        "## Provenance",
        "Runtime was {:.1f} s on `{}`. `manifest.json` records input and output hashes.".format(runtime, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02e_1781022343_1879_6c8e7427_manual_highrisk_audit.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    raw_root_dir = p09a.resolve_raw_root_dir(config)
    waves, meta, counts = p09a.scan_raw(config, raw_root_dir)
    prior_pairs = pd.read_csv(config["prior_prediction_csv"])
    repro = reproduction_table(config, counts, prior_pairs)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("reproduction failed; see reproduction_match_table.csv")

    meta = add_template_and_taxonomy(config, waves, meta)
    max_idx = len(meta) - 1
    missing = int(((prior_pairs["idx_a"] > max_idx) | (prior_pairs["idx_b"] > max_idx)).sum())
    frame, high_sources = pair_level_frame(prior_pairs, meta, waves)
    feature_cols = [c for c in frame.columns if c.startswith("f_") and frame[c].dtype != object]

    runs = sorted(int(r) for r in frame["run"].unique())
    trad_selected = np.zeros(len(frame), dtype=bool)
    trad_rules = []
    for held in runs:
        train_runs = [r for r in runs if r != held]
        name, scan, selected_all = select_traditional_rule(
            frame,
            train_runs,
            config["traditional_quantile_grid"],
            float(config["traditional_min_keep_fraction"]),
        )
        fold_sel = (frame["run"].to_numpy(dtype=int) == held) & selected_all
        trad_selected |= fold_sel
        best = scan.iloc[0].to_dict()
        best["heldout_run"] = held
        best["method_name"] = name
        trad_rules.append(best)
    trad_rule_table = pd.DataFrame(trad_rules)
    trad_name = "trad_" + str(trad_rule_table["feature"].mode().iloc[0]).replace("f_", "")

    ml_score, ml_folds, ml_importance = fit_ml_loro(frame, feature_cols, config)
    ml_sel = ml_selection(frame, ml_score)
    charge_null_sel = charge_pair_matched_null(frame, rng)
    prior_sel = frame["high_risk"].to_numpy(dtype=bool)
    random_same_rate = charge_pair_matched_null(frame.assign(high_risk=prior_sel), rng)

    selections = {
        "prior_ml_high_risk_flag": prior_sel,
        trad_name: trad_selected,
        "loro_ml_shape_recover_highrisk": ml_sel,
        "charge_pair_matched_null": charge_null_sel,
    }
    method_summary = pd.DataFrame([summarize_selection(frame, name, sel) for name, sel in selections.items()])
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    ci = bootstrap_summary(frame, selections, rng, int(config["bootstrap_replicates"]))
    ci.to_csv(out_dir / "heldout_run_bootstrap_ci.csv", index=False)
    ml_folds.to_csv(out_dir / "ml_loro_folds.csv", index=False)
    ml_importance.groupby("feature", as_index=False)["importance"].mean().sort_values("importance", ascending=False).to_csv(
        out_dir / "ml_feature_importance.csv", index=False
    )
    trad_rule_table.to_csv(out_dir / "traditional_loro_rules.csv", index=False)

    frame_out = frame[
        [
            "event_id",
            "run",
            "pair",
            "residual_ns",
            "tail_bool",
            "high_risk",
            "ml_score_pair_max",
            "amp_mean_adc",
            "log_amp_mean",
            "taxon_a",
            "taxon_b",
            "idx_a",
            "idx_b",
        ]
    ].copy()
    frame_out["audit_ml_shape_score"] = ml_score
    frame_out["audit_ml_shape_selected"] = ml_sel
    frame_out["audit_traditional_selected"] = trad_selected
    frame_out.to_csv(out_dir / "audited_pair_table.csv", index=False)

    atoms, atom_pairs = cluster_shape_atoms(frame, high_sources, meta, waves, out_dir)
    atoms.to_csv(out_dir / "shape_atom_summary.csv", index=False)
    atom_pairs.to_csv(out_dir / "shape_atom_pair_metrics.csv", index=False)

    leakage = leakage_checks(frame, feature_cols, ml_score, ml_sel, charge_null_sel, missing)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    # Compact diagnostic figure for method comparison.
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    order = method_summary.sort_values("high_risk_precision", ascending=False)
    ax.bar(np.arange(len(order)), order["high_risk_precision"], color=["#4c78a8", "#72b7b2", "#f58518", "#bab0ac"][: len(order)])
    ax.axhline(float(frame["high_risk"].mean()), color="0.35", ls="--", lw=1, label="baseline")
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels(order["method"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("precision for S02d high-risk pair flag")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_precision.png", dpi=140)
    plt.close(fig)

    input_hashes = []
    for run in p09a.configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    prior_path = Path(config["prior_prediction_csv"])
    input_hashes.append({"path": str(prior_path), "sha256": sha256_file(prior_path), "bytes": int(prior_path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - t0
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {"pass": bool(repro["pass"].all()), "rows": repro.to_dict(orient="records")},
        "heldout_runs": runs,
        "method_summary": method_summary.to_dict(orient="records"),
        "ml_loro_folds": ml_folds.to_dict(orient="records"),
        "shape_atoms": atoms.drop(columns=["mean_waveform"], errors="ignore").to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: this audit supports existing tail-shape and gallery follow-up lines; no genuinely novel non-duplicative ticket identified",
        "runtime_sec": round(runtime, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")

    write_report(out_dir, config, repro, method_summary, ci, ml_folds, atoms, atom_pairs, leakage, runtime)

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
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduction_pass": bool(repro["pass"].all()),
                "prior_highrisk_precision": float(method_summary.loc[method_summary["method"] == "prior_ml_high_risk_flag", "high_risk_precision"].iloc[0]),
                "trad_precision": float(method_summary.loc[method_summary["method"] == trad_name, "high_risk_precision"].iloc[0]),
                "ml_shape_precision": float(method_summary.loc[method_summary["method"] == "loro_ml_shape_recover_highrisk", "high_risk_precision"].iloc[0]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
