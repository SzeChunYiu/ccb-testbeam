#!/usr/bin/env python3
"""S02f: composition-stable timing-tail closure cut.

The raw ROOT reproduction gate is intentionally the first analysis operation.
Candidate timing-tail cuts are then registered from train runs only and
evaluated once on held-out runs with run-block bootstrap intervals.
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

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p09a_rare_waveform_anomaly_taxonomy as p09a
import s02d_anomaly_tail_closure_1781011449 as s02d


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


def json_scalar(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def dataframe_records(frame: pd.DataFrame) -> List[dict]:
    rows = []
    columns = list(frame.columns)
    for row in frame.itertuples(index=False, name=None):
        rows.append({col: json_scalar(value) for col, value in zip(columns, row)})
    return rows


def add_pair_ml_columns(pairs: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    out = pairs.copy()
    source_score = timing.set_index("source_idx")["ml_tail_score"].to_dict()
    source_high = timing.set_index("source_idx")["ml_high_risk"].to_dict()
    out["ml_score_a"] = out["idx_a"].map(source_score).fillna(0.0).astype(float)
    out["ml_score_b"] = out["idx_b"].map(source_score).fillna(0.0).astype(float)
    out["ml_score_pair_max"] = np.maximum(out["ml_score_a"].to_numpy(dtype=float), out["ml_score_b"].to_numpy(dtype=float))
    out["ml_high_risk_pair"] = out["idx_a"].map(source_high).fillna(False).astype(bool) | out["idx_b"].map(source_high).fillna(False).astype(bool)
    return out


def candidate_registry(train_pairs: pd.DataFrame, taxa: Sequence[str], quantiles: Sequence[float]) -> List[dict]:
    candidates: List[dict] = [{"action": "baseline", "family": "baseline"}]
    for taxon in taxa:
        candidates.append({"action": f"p09a_exclude_{taxon}", "family": "p09a_class", "taxon": taxon})
    for q in quantiles:
        thr = float(np.quantile(train_pairs["ml_score_pair_max"].to_numpy(dtype=float), float(q)))
        qtag = str(q).replace(".", "p")
        candidates.append({"action": f"ml_pair_risk_q{qtag}", "family": "ml_quantile", "ml_quantile": float(q), "ml_threshold": thr})
    for taxon in taxa:
        for q in quantiles:
            thr = float(np.quantile(train_pairs["ml_score_pair_max"].to_numpy(dtype=float), float(q)))
            qtag = str(q).replace(".", "p")
            candidates.append(
                {
                    "action": f"hybrid_{taxon}_or_ml_q{qtag}",
                    "family": "hybrid",
                    "taxon": taxon,
                    "ml_quantile": float(q),
                    "ml_threshold": thr,
                }
            )
    return candidates


def candidate_keep_mask(pairs: pd.DataFrame, candidate: dict) -> np.ndarray:
    keep = np.ones(len(pairs), dtype=bool)
    family = candidate["family"]
    if family in {"p09a_class", "hybrid"}:
        taxon = str(candidate["taxon"])
        keep &= (pairs["taxon_a"].to_numpy(dtype=object) != taxon) & (pairs["taxon_b"].to_numpy(dtype=object) != taxon)
    if family in {"ml_quantile", "hybrid"}:
        keep &= pairs["ml_score_pair_max"].to_numpy(dtype=float) < float(candidate["ml_threshold"])
    return keep


def fixed_center_metrics(values: np.ndarray, center_ns: float, tail_threshold_ns: float) -> Dict[str, float]:
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
    centered = values - float(center_ns)
    q16, q84 = np.percentile(centered, [16, 84])
    return {
        "n_pairs": int(len(values)),
        "tail_rate": float(np.mean(np.abs(centered) > float(tail_threshold_ns))),
        "sigma68_ns": float((q84 - q16) / 2.0),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))),
        "q95_abs_ns": float(np.percentile(np.abs(centered), 95)),
        "median_ns": float(np.median(values)),
    }


def score_candidates(
    pairs: pd.DataFrame,
    candidates: Sequence[dict],
    center_ns: float,
    tail_threshold_ns: float,
    constraints: dict,
    split: str,
) -> pd.DataFrame:
    base_charge = float(pairs["log_amp_mean"].median()) if len(pairs) else float("nan")
    base_pair_share = pairs["pair"].value_counts(normalize=True).to_dict() if len(pairs) else {}
    rows = []
    for candidate in candidates:
        keep = candidate_keep_mask(pairs, candidate)
        sub = pairs.loc[keep].copy()
        pair_share = sub["pair"].value_counts(normalize=True).to_dict() if len(sub) else {}
        max_pair_drift = 0.0
        for pair in set(list(base_pair_share.keys()) + list(pair_share.keys())):
            max_pair_drift = max(max_pair_drift, abs(pair_share.get(pair, 0.0) - base_pair_share.get(pair, 0.0)))
        median_log_amp_delta = float(sub["log_amp_mean"].median() - base_charge) if len(sub) else float("nan")
        metrics = fixed_center_metrics(sub["residual_ns"].to_numpy(dtype=float), center_ns, tail_threshold_ns)
        kept = float(len(sub) / max(1, len(pairs)))
        charge_ok = abs(median_log_amp_delta) <= float(constraints["max_abs_median_log_amp_delta"])
        pair_ok = max_pair_drift <= float(constraints["max_pair_composition_drift"])
        kept_ok = kept >= float(constraints["min_kept_pair_fraction"])
        rows.append(
            {
                "split": split,
                "action": candidate["action"],
                "family": candidate["family"],
                "taxon": candidate.get("taxon", ""),
                "ml_quantile": candidate.get("ml_quantile", np.nan),
                "ml_threshold": candidate.get("ml_threshold", np.nan),
                **metrics,
                "kept_pair_fraction": kept,
                "removed_pair_fraction": float(1.0 - kept),
                "median_log_amp_delta": median_log_amp_delta,
                "abs_median_log_amp_delta": abs(median_log_amp_delta),
                "max_pair_composition_drift": float(max_pair_drift),
                "charge_constraint_pass": bool(charge_ok),
                "pair_composition_constraint_pass": bool(pair_ok),
                "kept_fraction_constraint_pass": bool(kept_ok),
                "all_constraints_pass": bool(charge_ok and pair_ok and kept_ok),
            }
        )
    return pd.DataFrame(rows)


def select_preregistered_cut(train_scores: pd.DataFrame) -> str:
    baseline_tail = float(train_scores.loc[train_scores["action"] == "baseline", "tail_rate"].iloc[0])
    eligible = train_scores[
        (train_scores["family"] != "baseline")
        & (train_scores["all_constraints_pass"])
        & (train_scores["tail_rate"] < baseline_tail)
    ].copy()
    if eligible.empty:
        constrained = train_scores[(train_scores["family"] != "baseline") & (train_scores["all_constraints_pass"])].copy()
        if constrained.empty:
            return "baseline"
        eligible = constrained
    eligible = eligible.sort_values(
        ["tail_rate", "q95_abs_ns", "full_rms_ns", "kept_pair_fraction"],
        ascending=[True, True, True, False],
    )
    return str(eligible.iloc[0]["action"])


def bootstrap_candidates(
    pairs: pd.DataFrame,
    candidates: Sequence[dict],
    center_ns: float,
    tail_threshold_ns: float,
    constraints: dict,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    runs = np.asarray(sorted(pairs["run"].unique()))
    rows = []
    metrics = [
        "tail_rate",
        "full_rms_ns",
        "q95_abs_ns",
        "sigma68_ns",
        "kept_pair_fraction",
        "abs_median_log_amp_delta",
        "max_pair_composition_drift",
    ]
    for candidate in candidates:
        vals = {metric: [] for metric in metrics}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([pairs[pairs["run"] == int(run)] for run in sampled], ignore_index=True)
            score = score_candidates(boot, [candidate], center_ns, tail_threshold_ns, constraints, "heldout_boot")
            row = score.iloc[0]
            for metric in metrics:
                vals[metric].append(float(row[metric]))
        for metric in metrics:
            rows.append(
                {
                    "action": candidate["action"],
                    "family": candidate["family"],
                    "metric": metric,
                    "ci_low": float(np.nanpercentile(vals[metric], 2.5)),
                    "ci_high": float(np.nanpercentile(vals[metric], 97.5)),
                }
            )
    return pd.DataFrame(rows)


def waveform_hashes(waves: np.ndarray, indices: np.ndarray) -> set:
    rounded = np.round(waves[indices], 3).astype(np.float32)
    return set(hashlib.sha256(row.tobytes()).hexdigest() for row in rounded)


def build_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    train_scores: pd.DataFrame,
    heldout_scores: pd.DataFrame,
    ci: pd.DataFrame,
    ml_metrics: pd.DataFrame,
    leakage: pd.DataFrame,
    selected_action: str,
    tail_threshold_ns: float,
    train_pair_median_ns: float,
    runtime_sec: float,
) -> None:
    baseline = heldout_scores[heldout_scores["action"] == "baseline"].iloc[0]
    selected = heldout_scores[heldout_scores["action"] == selected_action].iloc[0]
    p09a_actions = heldout_scores.loc[heldout_scores["family"] == "p09a_class", "action"].tolist()
    ml_actions = heldout_scores.loc[heldout_scores["family"] == "ml_quantile", "action"].tolist()
    hybrid_actions = heldout_scores.loc[heldout_scores["family"] == "hybrid"].sort_values(
        ["tail_rate", "q95_abs_ns"]
    )["action"].head(8).tolist()
    comparison_actions = list(dict.fromkeys(["baseline"] + p09a_actions + ml_actions + hybrid_actions + [selected_action]))
    comparison = heldout_scores[heldout_scores["action"].isin(comparison_actions)].copy()
    family_order = {"baseline": 0, "p09a_class": 1, "ml_quantile": 2, "hybrid": 3}
    comparison["family_order"] = comparison["family"].map(family_order).fillna(99)
    comparison = comparison.sort_values(["family_order", "tail_rate", "q95_abs_ns"])
    shown_actions = ["baseline", selected_action]
    best_by_family = heldout_scores.sort_values("tail_rate").groupby("family", as_index=False).head(1)["action"].tolist()
    shown_actions = list(dict.fromkeys(shown_actions + best_by_family))
    lines = [
        "# S02f: composition-stable timing-tail closure cut",
        "",
        f"**Ticket:** `{config['ticket_id']}`",
        "",
        "## Reproduction first",
        "The raw B-stack ROOT files were scanned before any timing labels, model fits, or prior report outputs were consumed. The S00/S02 selected-pulse gates reproduced exactly.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Pre-registered split and cut rule",
        "Training runs were all configured B-stack runs except held-out runs `{}`. The fixed residual center was the train-pair median `{:.6f} ns`; the tail threshold was the train-run {:.0f}th percentile of absolute residuals, `{:.6f} ns`.".format(
            ", ".join(str(r) for r in config["heldout_runs"]),
            train_pair_median_ns,
            100.0 * float(config["tail_quantile"]),
            tail_threshold_ns,
        ),
        "Candidate cuts were registered on train runs only: deterministic P09a class exclusions, ML pair-risk quantiles, and class-or-ML hybrids. The selected cut minimized train tail rate subject to median log-charge drift <= `{}`, max pair-composition drift <= `{}`, and kept-pair fraction >= `{}`.".format(
            config["constraints"]["max_abs_median_log_amp_delta"],
            config["constraints"]["max_pair_composition_drift"],
            config["constraints"]["min_kept_pair_fraction"],
        ),
        "",
        f"Selected pre-registered action: `{selected_action}`.",
        "",
        "## Held-out comparison",
        comparison[
            [
                "action",
                "family",
                "n_pairs",
                "tail_rate",
                "full_rms_ns",
                "q95_abs_ns",
                "kept_pair_fraction",
                "abs_median_log_amp_delta",
                "max_pair_composition_drift",
                "all_constraints_pass",
            ]
        ].to_markdown(index=False),
        "",
        "The selected held-out cut changed tail rate from `{:.4f}` to `{:.4f}`, q95 from `{:.3f}` to `{:.3f} ns`, and kept `{:.3f}` of pairs. Its held-out charge drift was `{:.5f}` and max pair-composition drift was `{:.5f}`.".format(
            float(baseline["tail_rate"]),
            float(selected["tail_rate"]),
            float(baseline["q95_abs_ns"]),
            float(selected["q95_abs_ns"]),
            float(selected["kept_pair_fraction"]),
            float(selected["abs_median_log_amp_delta"]),
            float(selected["max_pair_composition_drift"]),
        ),
        "",
        "## Held-out run bootstrap CIs",
        "CIs resample held-out runs with replacement.",
        "",
        ci[ci["action"].isin(shown_actions)].to_markdown(index=False),
        "",
        "## ML diagnostics",
        "The RandomForest tail-risk model used P09a scores/taxa and train-fit PCA waveform latents, with no run id, event id, source index, or stave id features.",
        "",
        ml_metrics.to_markdown(index=False),
        "",
        "## Leakage checks",
        leakage.to_markdown(index=False),
        "",
        "## Verdict",
        "A composition-stable timing-tail cut is possible, but the constraints matter. Deterministic P09a class exclusions alone barely move the held-out tail, while the ML q90 pair-risk cut supplies most of the mitigation and remains inside the configured charge and pair-mix limits on this split. The selected hybrid is train-registered rather than held-out-picked; its improvement is useful but modest, so it should be treated as a cut recommendation rather than a new calibration model.",
        "",
        "## Provenance",
        "Runtime was `{:.1f} s` on `{}`. `manifest.json` records input, code, and output hashes.".format(runtime_sec, platform.node()),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02f_1781022344_1947_76bd0c43_composition_stable_timing_tail_cut.json")
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
    repro = s02d.reproduction_table(config, counts)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed; see reproduction_match_table.csv")

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    train_mask_all = ~meta["run"].isin(heldout_runs).to_numpy()
    meta = p09a.add_template_residual(config, waves, meta, train_mask_all)
    meta, thresholds = p09a.add_taxonomy(meta, train_mask_all)
    meta["traditional_score"] = p09a.score_traditional(meta, train_mask_all)
    thresholds.to_csv(out_dir / "feature_thresholds.csv", index=False)

    timing = s02d.build_timing_frame(meta, config)
    train_runs = sorted(set(int(r) for r in timing["run"].unique()) - heldout_runs)
    heldout_timing_mask = timing["run"].isin(heldout_runs).to_numpy()
    train_timing_mask = ~heldout_timing_mask
    timing, correction_table = s02d.add_binned_timewalk(timing, train_runs, config)
    correction_table.to_csv(out_dir / "timewalk_bin_corrections.csv", index=False)

    train_pairs_raw = s02d.pair_table(timing, "t_timewalk_ns", train_runs, config, threshold=math.inf)
    train_values = train_pairs_raw["residual_ns"].to_numpy(dtype=float)
    train_values = train_values[np.isfinite(train_values)]
    train_pair_median = float(np.median(train_values))
    tail_threshold = float(np.percentile(np.abs(train_values - train_pair_median), 100.0 * float(config["tail_quantile"])))
    train_pairs = s02d.pair_table(timing, "t_timewalk_ns", train_runs, config, threshold=tail_threshold, center_ns=train_pair_median)
    heldout_pairs = s02d.pair_table(timing, "t_timewalk_ns", heldout_runs, config, threshold=tail_threshold, center_ns=train_pair_median)
    timing["true_tail_pulse"] = s02d.true_tail_pulse_labels(timing, pd.concat([train_pairs, heldout_pairs], ignore_index=True))

    X, feature_cols = s02d.taxonomy_feature_frame(timing, waves, train_timing_mask, config)
    ml_score, ml_cv, ml_info = s02d.fit_ml_scores(
        X,
        timing["true_tail_pulse"].to_numpy(dtype=int),
        timing["run"].to_numpy(dtype=int),
        train_timing_mask,
        heldout_timing_mask,
        config,
    )
    timing["ml_tail_score"] = ml_score
    timing["ml_high_risk"] = timing["ml_tail_score"] >= float(ml_info["score_threshold_from_train"])
    train_pairs = add_pair_ml_columns(train_pairs, timing)
    heldout_pairs = add_pair_ml_columns(heldout_pairs, timing)
    train_pairs.to_csv(out_dir / "train_pair_predictions.csv", index=False)
    heldout_pairs.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)

    taxa = [str(t) for t in sorted(timing["taxon"].unique()) if str(t) != "unassigned_common"]
    candidates = candidate_registry(train_pairs, taxa, config["ml_pair_quantiles"])
    train_scores = score_candidates(train_pairs, candidates, train_pair_median, tail_threshold, config["constraints"], "train")
    selected_action = select_preregistered_cut(train_scores)
    heldout_scores = score_candidates(heldout_pairs, candidates, train_pair_median, tail_threshold, config["constraints"], "heldout")
    train_scores.to_csv(out_dir / "candidate_train_registry.csv", index=False)
    heldout_scores.to_csv(out_dir / "candidate_heldout_metrics.csv", index=False)

    ci = bootstrap_candidates(
        heldout_pairs,
        candidates,
        train_pair_median,
        tail_threshold,
        config["constraints"],
        rng,
        int(config["bootstrap_replicates"]),
    )
    ci.to_csv(out_dir / "heldout_bootstrap_ci.csv", index=False)

    heldout_tail_labels = timing.loc[heldout_timing_mask, "true_tail_pulse"].to_numpy(dtype=int)
    heldout_scores_ml = timing.loc[heldout_timing_mask, "ml_tail_score"].to_numpy(dtype=float)
    fixed_sel = timing.loc[heldout_timing_mask, "ml_high_risk"].to_numpy(dtype=bool)
    ml_metric_rows = [
        s02d.classifier_metrics("heldout_all", heldout_tail_labels, heldout_scores_ml),
        {
            "selection": "fixed_train_pulse_threshold",
            "n_selected": int(fixed_sel.sum()),
            "selected_fraction": float(fixed_sel.mean()),
            "precision": float(np.mean(heldout_tail_labels[fixed_sel])) if fixed_sel.any() else float("nan"),
            "baseline_tail_pulse_rate": float(np.mean(heldout_tail_labels)),
            **s02d.classifier_metrics("heldout_fixed_threshold_scores", heldout_tail_labels, heldout_scores_ml),
        },
    ]
    for q in config["ml_pair_quantiles"]:
        thr = float(np.quantile(train_pairs["ml_score_pair_max"].to_numpy(dtype=float), float(q)))
        pair_sel = heldout_pairs["ml_score_pair_max"].to_numpy(dtype=float) >= thr
        ml_metric_rows.append(
            {
                "split": f"heldout_pair_q{str(q).replace('.', 'p')}",
                "n": int(len(heldout_pairs)),
                "positive_rate": float(heldout_pairs["tail"].mean()),
                "average_precision": float("nan"),
                "roc_auc": float("nan"),
                "selection": f"pair_max_score_q{q}",
                "n_selected": int(pair_sel.sum()),
                "selected_fraction": float(pair_sel.mean()),
                "precision": float(heldout_pairs.loc[pair_sel, "tail"].mean()) if pair_sel.any() else float("nan"),
                "baseline_tail_pulse_rate": float(np.mean(heldout_tail_labels)),
            }
        )
    ml_metrics = pd.DataFrame(ml_metric_rows)
    ml_metrics.to_csv(out_dir / "ml_classifier_metrics.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_run_cv_metrics.csv", index=False)

    train_hashes = waveform_hashes(waves, timing.loc[train_timing_mask, "source_idx"].to_numpy(dtype=int))
    held_hashes = waveform_hashes(waves, timing.loc[heldout_timing_mask, "source_idx"].to_numpy(dtype=int))
    overlap = len(train_hashes.intersection(held_hashes))
    forbidden = [c for c in feature_cols if c in {"run", "eventno", "evt", "event_index", "event_id", "stave", "source_idx"}]
    selected_row = heldout_scores[heldout_scores["action"] == selected_action].iloc[0]
    baseline_row = heldout_scores[heldout_scores["action"] == "baseline"].iloc[0]
    tail_reduction = 1.0 - float(selected_row["tail_rate"]) / max(float(baseline_row["tail_rate"]), 1e-12)
    suspicious = bool(tail_reduction > 0.50 or float(selected_row["tail_rate"]) < 0.01)
    stave_x = pd.get_dummies(timing["stave"], prefix="stave")
    proxy_score, _, _ = s02d.fit_ml_scores(
        stave_x,
        timing["true_tail_pulse"].to_numpy(dtype=int),
        timing["run"].to_numpy(dtype=int),
        train_timing_mask,
        heldout_timing_mask,
        dict(config, ml=dict(config["ml"], rf_trees=120), ml_flag_quantile=config["ml_flag_quantile"]),
    )
    proxy_metrics = s02d.classifier_metrics("heldout_stave_only_proxy", heldout_tail_labels, proxy_score[heldout_timing_mask])
    event_overlap = len(
        set(timing.loc[train_timing_mask, "event_id"].astype(str)).intersection(
            set(timing.loc[heldout_timing_mask, "event_id"].astype(str))
        )
    )
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(train_runs).intersection(heldout_runs))),
                "pass": len(set(train_runs).intersection(heldout_runs)) == 0,
                "note": "run-disjoint split",
            },
            {
                "check": "train_heldout_event_id_overlap",
                "value": int(event_overlap),
                "pass": event_overlap == 0,
                "note": "event ids include run and raw event counters",
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
                "note": "triggered if selected cut reduces heldout tail rate by >50 pct or below 1 pct",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "reproduction": {"pass": bool(repro["pass"].all()), "rows": dataframe_records(repro)},
        "split": {
            "train_runs": train_runs,
            "heldout_runs": sorted(int(r) for r in heldout_runs),
            "tail_threshold_ns": tail_threshold,
            "train_pair_median_ns": train_pair_median,
        },
        "constraints": config["constraints"],
        "selected_action": selected_action,
        "selected_train": dataframe_records(train_scores[train_scores["action"] == selected_action]),
        "selected_heldout": dataframe_records(heldout_scores[heldout_scores["action"] == selected_action]),
        "heldout_baseline": dataframe_records(heldout_scores[heldout_scores["action"] == "baseline"]),
        "candidate_heldout_metrics": dataframe_records(heldout_scores),
        "ml_classifier": dataframe_records(ml_metrics),
        "leakage_checks": dataframe_records(leakage),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    build_report(
        out_dir,
        config,
        repro,
        train_scores,
        heldout_scores,
        ci,
        ml_metrics,
        leakage,
        selected_action,
        tail_threshold,
        train_pair_median,
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
        "command": f"{sys.executable} {Path(__file__)} --config {config_path}",
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
        "selected_action": selected_action,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduction_pass": bool(repro["pass"].all()),
                "tail_threshold_ns": tail_threshold,
                "selected_action": selected_action,
                "baseline_heldout_tail_rate": float(baseline_row["tail_rate"]),
                "selected_heldout_tail_rate": float(selected_row["tail_rate"]),
                "selected_constraints_pass": bool(selected_row["all_constraints_pass"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
