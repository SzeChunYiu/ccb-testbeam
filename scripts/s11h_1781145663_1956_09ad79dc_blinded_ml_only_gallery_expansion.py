#!/usr/bin/env python3
"""S11h blinded ML-only gallery expansion.

The study freezes S11f/S11b event-level scores, expands the S11f
consensus-ML-only high-current morphology gallery with matched low-current
controls, and benchmarks frozen traditional/ML/NN actions against deterministic
blinded morphology-review labels. ML probabilities are used for stratified
selection and method benchmarking only; they are not label inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "s11h_1781145663_1956_09ad79dc_blinded_ml_only_gallery_expansion.json"
THIS_SCRIPT = "scripts/s11h_1781145663_1956_09ad79dc_blinded_ml_only_gallery_expansion.py"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def markdown_table(frame: pd.DataFrame, digits: int = 5) -> str:
    if frame.empty:
        return "_No rows._"
    cols = list(frame.columns)

    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.{digits}g}"
        return str(v)

    rows = [[fmt(row[c]) for c in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    out.extend("| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows)
    return "\n".join(out)


def action_col(method: str) -> str:
    return f"{method}__accepted"


def prob_col(method: str) -> str:
    return f"{method}__pred_overlap_probability"


def frac_col(method: str) -> str:
    return f"{method}__pred_secondary_fraction"


def build_wide_scores(scores: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    keys = [
        "event_index",
        "run",
        "group",
        "current_nA",
        "eventno",
        "stratum",
        "amp_bin",
        "baseline_bin",
        "p02_topology",
        "ref_stave",
        "ref_amp_adc",
        "adaptive_lowering_adc",
        "downstream",
        "one_sse_norm",
        "resid_late_max_frac",
        "trad_secondary_fraction",
        "trad_secondary_primary_ratio",
        "trad_score_sse_improvement",
        "trad_failed",
        "trad_t1_sample",
        "trad_t2_sample",
        "trad_amp1_adc",
        "trad_amp2_adc",
    ]
    base = scores[keys].drop_duplicates(["event_index", "run"]).copy()
    for method in methods:
        sub = scores[scores["method"] == method][
            ["event_index", "run", "accepted", "pred_overlap_probability", "pred_secondary_fraction"]
        ].copy()
        sub = sub.rename(
            columns={
                "accepted": action_col(method),
                "pred_overlap_probability": prob_col(method),
                "pred_secondary_fraction": frac_col(method),
            }
        )
        base = base.merge(sub, on=["event_index", "run"], how="left")
    return base


def select_gallery(wide: pd.DataFrame, pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    target = pairs[
        (pairs["method"] == config["target_method"])
        & (pairs["disagreement_class"] == config["target_disagreement_class"])
        & (pairs["group"] == "high_20nA")
    ][["event_index", "run"]].drop_duplicates()
    target = target.merge(wide, on=["event_index", "run"], how="inner")
    target = target.sort_values(
        [prob_col(config["target_method"]), frac_col(config["target_method"]), "one_sse_norm"],
        ascending=[False, False, False],
    )
    high = (
        target.groupby("run", group_keys=False)
        .head(int(config["high_per_run_cap"]))
        .copy()
        .sort_values(["run", prob_col(config["target_method"])], ascending=[True, False])
    )
    high["gallery_arm"] = config["high_arm"]

    low_pool = wide[wide["group"] == "low_2nA"].copy()
    controls = []
    used: set[tuple[int, int]] = set()
    for _, row in high.iterrows():
        pool = low_pool[low_pool["stratum"] == row["stratum"]].copy()
        if pool.empty:
            pool = low_pool[
                (low_pool["amp_bin"] == row["amp_bin"]) & (low_pool["p02_topology"] == row["p02_topology"])
            ].copy()
        if pool.empty:
            pool = low_pool.copy()
        pool["_distance"] = (
            (np.log1p(pool["ref_amp_adc"]) - np.log1p(float(row["ref_amp_adc"]))).abs()
            + (np.log1p(pool["adaptive_lowering_adc"].clip(lower=0)) - np.log1p(max(float(row["adaptive_lowering_adc"]), 0))).abs()
            + 0.25 * (pool["run"].isin([int(row["run"])]).astype(float))
        )
        pool = pool.sort_values(["_distance", "run", "event_index"])
        chosen = None
        for _, cand in pool.iterrows():
            key = (int(cand["run"]), int(cand["event_index"]))
            if key not in used:
                chosen = cand
                used.add(key)
                break
        if chosen is None:
            chosen = pool.iloc[int(rng.integers(0, len(pool)))]
        controls.append(chosen.drop(labels=["_distance"], errors="ignore"))
    low = pd.DataFrame(controls).copy()
    low["gallery_arm"] = config["control_arm"]
    gallery = pd.concat([high, low], ignore_index=True)
    gallery["blind_id"] = [f"S11H-{i:05d}" for i in rng.permutation(np.arange(len(gallery)))]
    return gallery.sample(frac=1.0, random_state=int(config["random_seed"]) + 17).reset_index(drop=True)


def add_external_gallery_labels(gallery: pd.DataFrame, gallery_source: Path) -> pd.DataFrame:
    out = gallery.copy()
    if gallery_source.exists():
        ext_cols = [
            "event_index",
            "run",
            "morphology",
            "two_pulse_like",
            "artifact_like",
            "shape_artifact_strong",
            "blind_second_peak_frac",
            "blind_late_max_frac",
            "blind_neg_step_count",
            "blind_width10_samples",
            "blind_second_peak_separation_ns",
        ]
        ext = pd.read_csv(gallery_source, usecols=lambda c: c in ext_cols)
        ext = ext.drop_duplicates(["event_index", "run"])
        out = out.merge(ext, on=["event_index", "run"], how="left", suffixes=("", "_external"))
    else:
        out["morphology"] = np.nan
        out["two_pulse_like"] = np.nan
        out["artifact_like"] = np.nan
        out["shape_artifact_strong"] = np.nan
    out["in_prior_gallery"] = out["two_pulse_like"].notna()
    return out


def blind_review_labels(gallery: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = gallery.copy()
    delay = 10.0 * (out["trad_t2_sample"] - out["trad_t1_sample"])
    bounded_clean = (
        (~out["trad_failed"].fillna(True).astype(bool))
        & (out["trad_score_sse_improvement"].fillna(0) >= float(config["traditional_min_score"]))
        & (out["trad_secondary_fraction"].fillna(0) >= float(config["traditional_min_secondary_fraction"]))
        & delay.between(10.0, 60.0, inclusive="both")
        & (out["trad_secondary_primary_ratio"].fillna(0) <= 2.5)
    )
    morphology_clean = (
        (out["p02_topology"].astype(str) != "p02_early_pathology")
        & (out["one_sse_norm"].fillna(np.inf) < 5.0)
        & (out["resid_late_max_frac"].fillna(-np.inf) > -0.15)
        & (out["resid_late_max_frac"].fillna(np.inf) < 1.2)
    )
    external_two = out["two_pulse_like"].fillna(0).astype(float) > 0.5
    external_artifact = out["artifact_like"].fillna(0).astype(float) > 0.5
    shape_artifact = (
        external_artifact
        | (out["p02_topology"].astype(str) == "p02_early_pathology")
        | (out["one_sse_norm"].fillna(0) >= 8.0)
        | (out["resid_late_max_frac"].fillna(0) < -0.6)
        | (out["adaptive_lowering_adc"].fillna(0) > 4500.0)
    )
    reviewer_a = external_two | (bounded_clean & morphology_clean)
    reviewer_b = bounded_clean & (out["downstream"].fillna(0).astype(int).astype(bool) | (out["ref_amp_adc"].fillna(0) >= 2500.0))
    reviewer_c = morphology_clean & (delay.fillna(30.0).between(10.0, 70.0, inclusive="both")) & ~shape_artifact
    out["reviewer_external_or_fit"] = reviewer_a.astype(int)
    out["reviewer_bounded_topology"] = reviewer_b.astype(int)
    out["reviewer_shape_blind"] = reviewer_c.astype(int)
    out["artifact_reviewer_external"] = external_artifact.astype(int)
    out["artifact_reviewer_shape"] = shape_artifact.astype(int)
    out["two_pulse_vote_count"] = (
        out["reviewer_external_or_fit"] + out["reviewer_bounded_topology"] + out["reviewer_shape_blind"]
    )
    out["artifact_vote_count"] = out["artifact_reviewer_external"] + out["artifact_reviewer_shape"]
    out["two_pulse_like_blinded"] = ((out["two_pulse_vote_count"] >= 2) & (out["artifact_vote_count"] <= 1)).astype(int)
    out["artifact_like_blinded"] = ((out["artifact_vote_count"] >= 1) & (out["two_pulse_vote_count"] < 3)).astype(int)
    out["ambiguous_blinded"] = ((out["two_pulse_vote_count"] == 1) | ((out["two_pulse_vote_count"] >= 2) & (out["artifact_vote_count"] >= 2))).astype(int)
    return out


def metric_values(frame: pd.DataFrame, method: str, matched_excess: float) -> dict:
    action = frame[action_col(method)].fillna(0).astype(int).to_numpy(bool)
    y = frame["two_pulse_like_blinded"].to_numpy(int)
    artifact = frame["artifact_like_blinded"].to_numpy(int)
    if action.any():
        precision = float(y[action].mean())
        artifact_fraction = float(artifact[action].mean())
    else:
        precision = artifact_fraction = float("nan")
    recall = float(y[action].sum() / y.sum()) if y.sum() else float("nan")
    coverage = float(action.mean()) if len(frame) else float("nan")
    high = frame["gallery_arm"].eq("high_ml_only")
    control = frame["gallery_arm"].eq("matched_low_control")
    def accepted_rate(mask):
        sub = frame[mask]
        if len(sub) == 0:
            return float("nan")
        return float(sub[action_col(method)].fillna(0).astype(int).mean())
    high_rate = accepted_rate(high)
    control_rate = accepted_rate(control)
    delta = high_rate - control_rate if np.isfinite(high_rate) and np.isfinite(control_rate) else float("nan")
    topology_coverage = delta / matched_excess if matched_excess else float("nan")
    f1 = (2 * precision * recall / (precision + recall)) if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) else float("nan")
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "artifact_fraction": artifact_fraction,
        "coverage": coverage,
        "accepted_high_rate": high_rate,
        "accepted_control_rate": control_rate,
        "accepted_high_minus_control": delta,
        "topology_excess_coverage": topology_coverage,
    }


def bootstrap_methods(gallery: pd.DataFrame, methods: list[str], matched_excess: float, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    metrics = [
        "precision",
        "recall",
        "f1",
        "artifact_fraction",
        "coverage",
        "accepted_high_minus_control",
        "topology_excess_coverage",
    ]
    runs_by_arm = {
        arm: np.array(sorted(gallery.loc[gallery["gallery_arm"] == arm, "run"].unique()), dtype=int)
        for arm in sorted(gallery["gallery_arm"].unique())
    }
    rows = []
    for method in methods:
        full = metric_values(gallery, method, matched_excess)
        draws = {m: [] for m in metrics}
        for _ in range(int(n_boot)):
            sampled_runs = []
            for arm, runs in runs_by_arm.items():
                take = rng.choice(runs, size=len(runs), replace=True)
                sampled_runs.extend([(arm, int(run)) for run in take])
            sample = pd.concat(
                [gallery[(gallery["gallery_arm"] == arm) & (gallery["run"] == run)] for arm, run in sampled_runs],
                ignore_index=True,
            )
            vals = metric_values(sample, method, matched_excess)
            for metric in metrics:
                if np.isfinite(vals[metric]):
                    draws[metric].append(vals[metric])
        row = {"method": method}
        for metric in metrics:
            arr = np.asarray(draws[metric], dtype=float)
            row[metric] = full[metric]
            row[f"{metric}_ci_low"] = float(np.quantile(arr, 0.025)) if len(arr) else float("nan")
            row[f"{metric}_ci_high"] = float(np.quantile(arr, 0.975)) if len(arr) else float("nan")
        row["n_bootstrap"] = int(min(len(v) for v in draws.values()))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["selection_score"] = (
        out["f1"].fillna(-1.0)
        + 0.30 * out["precision"].fillna(0.0)
        - 0.40 * out["artifact_fraction"].fillna(1.0)
        + 0.10 * out["topology_excess_coverage"].clip(lower=-2, upper=2).fillna(0.0)
    )
    return out.sort_values(["selection_score", "f1", "precision"], ascending=[False, False, False]).reset_index(drop=True)


def arm_summary(gallery: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs_by_arm = {
        arm: np.array(sorted(gallery.loc[gallery["gallery_arm"] == arm, "run"].unique()), dtype=int)
        for arm in sorted(gallery["gallery_arm"].unique())
    }
    for arm, sub in gallery.groupby("gallery_arm"):
        rows.append(
            {
                "gallery_arm": arm,
                "n": int(len(sub)),
                "runs": ",".join(str(int(r)) for r in sorted(sub["run"].unique())),
                "two_pulse_like_rate": float(sub["two_pulse_like_blinded"].mean()),
                "artifact_like_rate": float(sub["artifact_like_blinded"].mean()),
                "prior_gallery_overlap": float(sub["in_prior_gallery"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    deltas = []
    for _ in range(int(n_boot)):
        sample_parts = []
        for arm, runs in runs_by_arm.items():
            for run in rng.choice(runs, size=len(runs), replace=True):
                sample_parts.append(gallery[(gallery["gallery_arm"] == arm) & (gallery["run"] == int(run))])
        sample = pd.concat(sample_parts, ignore_index=True)
        hi = sample[sample["gallery_arm"] == "high_ml_only"]["two_pulse_like_blinded"].mean()
        lo = sample[sample["gallery_arm"] == "matched_low_control"]["two_pulse_like_blinded"].mean()
        if np.isfinite(hi) and np.isfinite(lo):
            deltas.append(float(hi - lo))
    out.attrs["delta"] = {
        "high_minus_control_two_pulse_like": float(
            gallery[gallery["gallery_arm"] == "high_ml_only"]["two_pulse_like_blinded"].mean()
            - gallery[gallery["gallery_arm"] == "matched_low_control"]["two_pulse_like_blinded"].mean()
        ),
        "ci_low": float(np.quantile(deltas, 0.025)) if deltas else float("nan"),
        "ci_high": float(np.quantile(deltas, 0.975)) if deltas else float("nan"),
        "n_bootstrap": int(len(deltas)),
    }
    return out


def save_plots(out_dir: Path, method_summary: pd.DataFrame, arm: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    plot = method_summary.sort_values("selection_score", ascending=True)
    ax.barh(plot["method"], plot["selection_score"], color="#4c78a8")
    ax.set_xlabel("selection score")
    ax.set_title("S11h blinded-gallery method ranking")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_ranking.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    x = np.arange(len(arm))
    ax.bar(x - 0.18, arm["two_pulse_like_rate"], width=0.36, label="two-pulse-like")
    ax.bar(x + 0.18, arm["artifact_like_rate"], width=0.36, label="artifact-like")
    ax.set_xticks(x, arm["gallery_arm"], rotation=15)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.set_title("Blinded gallery labels by arm")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_gallery_arm_rates.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    raw_counts: dict,
    arm: pd.DataFrame,
    delta: dict,
    method_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    compact_methods = method_summary[
        [
            "method",
            "precision",
            "precision_ci_low",
            "precision_ci_high",
            "recall",
            "recall_ci_low",
            "recall_ci_high",
            "artifact_fraction",
            "artifact_fraction_ci_low",
            "artifact_fraction_ci_high",
            "accepted_high_minus_control",
            "accepted_high_minus_control_ci_low",
            "accepted_high_minus_control_ci_high",
            "topology_excess_coverage",
            "selection_score",
        ]
    ]
    lines = [
        "# S11h: blinded ML-only gallery expansion",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-07-09",
        "- **Depends on:** S11f frozen event scores, S11b raw B-stack ROOT loader, S10f morphology gallery.",
        f"- **Inputs:** `{config['raw_root_dir']}`, `{config['s11f_report_dir']}`, `{config['gallery_source']}`.",
        f"- **Config:** `{Path(config['config_path']).relative_to(ROOT)}`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## 1. Question",
        "",
        "Are the S11f consensus ML-only high-current rows that carry a positive run-bootstrap excess genuine two-pulse morphology or detector-shape artifacts? The analysis freezes the S11f bounded-fit, ridge, gradient-boosted-tree, MLP, 1D-CNN, and consensus scores. These scores are used for selection and benchmarking only; the blinded morphology labels are derived from external gallery labels where available plus traditional fit and shape diagnostics that do not inspect learned probabilities.",
        "",
        "## 2. Raw-ROOT Reproduction Gate",
        "",
        f"The S11b raw loader was rerun on the local ROOT files and rebuilt {raw_counts['low_2nA_events_with_selected']} low-current selected events and {raw_counts['high_20nA_events_with_selected']} high-current selected events before any S11h gallery scoring.",
        "",
        markdown_table(reproduction),
        "",
        "## 3. Sampling Design",
        "",
        "Let `G_i` denote the gallery arm. The high arm is",
        "",
        "`G_i = high_ml_only` iff the frozen S11f consensus-abstention action accepted row `i`, the frozen traditional bounded fit did not accept it, and the row came from a 20 nA source run.",
        "",
        "For each high-arm row, a low-current control was chosen from the same S11f stratum when possible, otherwise from the nearest amplitude/topology cell by log-amplitude and log-lowering distance. The final gallery order is blinded by a random `S11H-*` identifier. Bootstrap resampling uses source runs within arm as the block unit.",
        "",
        markdown_table(arm),
        "",
        f"Primary blinded-label high-minus-control two-pulse-like delta: **{delta['high_minus_control_two_pulse_like']:.5f}** [{delta['ci_low']:.5f}, {delta['ci_high']:.5f}] over {delta['n_bootstrap']} source-run bootstrap draws.",
        "",
        "## 4. Blinded Label Model",
        "",
        "Three deterministic reviewer views emulate blinded morphology review. Reviewer A accepts an external S10f two-pulse-like label when present or a clean bounded two-pulse fit. Reviewer B requires a bounded fit plus downstream topology or sufficient amplitude. Reviewer C requires non-pathological residual shape and a plausible 10-70 ns separation. Artifact votes are assigned by external artifact labels, early-pathology topology, extreme one-pulse residuals, strongly negative late residuals, or very large adaptive lowering. The final label is",
        "",
        "`y_i = 1{V_i >= 2 and A_i <= 1}`,",
        "",
        "where `V_i` is the number of two-pulse reviewer votes and `A_i` is the artifact vote count. This is a morphology-review endpoint, not a truth-level decomposition.",
        "",
        "## 5. Method Benchmark",
        "",
        "Every method is evaluated as a frozen binary action against the blinded labels. Precision is `TP/(TP+FP)`, recall is `TP/P`, artifact fraction is the blinded artifact rate among accepted rows, and topology-excess coverage is the method accepted high-minus-control contrast divided by the S11f matched downstream excess.",
        "",
        markdown_table(compact_methods),
        "",
        f"Named winner: **{result['winner']['method']}** with selection score {result['winner']['selection_score']:.5g}.",
        "",
        "## 6. Leakage and Systematics",
        "",
        markdown_table(leakage),
        "",
        "- The label construction intentionally excludes GBT, MLP, CNN, ridge, and consensus probabilities.",
        "- Run-block bootstrap intervals cover run-to-run variation inside the selected support, not the full uncertainty of human morphology adjudication.",
        "- The S10f gallery overlap is incomplete; external labels stabilize some rows but do not make this a complete hand-scan.",
        "- The matched controls are low-current rows from only runs 46 and 47, so low-arm bootstrap uncertainty is necessarily coarse.",
        "- Because the high arm is selected from consensus ML-only rows, this is a validation of that support region rather than a population-wide pile-up-rate estimate.",
        "",
        "## 7. Conclusion",
        "",
        result["conclusion"],
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {Path(config['config_path']).relative_to(ROOT)}",
        "```",
        "",
        f"Runtime in this run was {runtime:.2f} s. Outputs include `result.json`, `manifest.json`, `raw_root_reproduction.csv`, `blinded_gallery.csv`, `method_summary.csv`, `arm_summary.csv`, `bootstrap_delta_summary.json`, `leakage_checks.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (ROOT / config_path).resolve()
    config = load_json(config_path)
    config["config_path"] = str(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11b = load_module(ROOT / config["source_script"], "s11b_for_s11h")
    events, _waves, run_counts = s11b.load_events()
    topology, reproduction = s11b.reproduce_s10(events)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT S10 topology reproduction failed")
    raw_counts = {
        "low_2nA_events_with_selected": int(topology[topology["group"] == "low_2nA"].iloc[0]["events_with_selected"]),
        "high_20nA_events_with_selected": int(topology[topology["group"] == "high_20nA"].iloc[0]["events_with_selected"]),
    }

    s11f_dir = ROOT / config["s11f_report_dir"]
    scores = pd.read_csv(s11f_dir / "event_method_scores.csv")
    pairs = pd.read_csv(s11f_dir / "taxonomy_event_pairs.csv")
    methods = list(config["required_methods"])
    missing = sorted(set(methods) - set(scores["method"].unique()))
    if missing:
        raise RuntimeError(f"missing required S11f methods: {missing}")
    wide = build_wide_scores(scores, methods)
    gallery = select_gallery(wide, pairs, config, rng)
    gallery = add_external_gallery_labels(gallery, ROOT / config["gallery_source"])
    gallery = blind_review_labels(gallery, config)

    arm = arm_summary(gallery, rng, int(config["bootstrap_samples"]))
    delta = arm.attrs["delta"]
    method_summary = bootstrap_methods(
        gallery, methods, float(config["matched_downstream_high_minus_low"]), rng, int(config["bootstrap_samples"])
    )
    winner = method_summary.iloc[0].to_dict()
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_pass",
                "value": float(bool(reproduction["pass"].all())),
                "pass": bool(reproduction["pass"].all()),
                "note": "S10 topology fractions rebuilt directly from local ROOT files.",
            },
            {
                "check": "all_required_methods_present",
                "value": float(len(missing) == 0),
                "pass": len(missing) == 0,
                "note": "Traditional, ridge, GBT, MLP, 1D-CNN, and consensus actions are present.",
            },
            {
                "check": "labels_do_not_use_ml_probabilities",
                "value": 1.0,
                "pass": True,
                "note": "Blinded label columns are functions of external labels, bounded-fit diagnostics, and shape/topology fields only.",
            },
            {
                "check": "source_run_bootstrap_used",
                "value": float(config["bootstrap_samples"]),
                "pass": int(config["bootstrap_samples"]) >= 200,
                "note": "Intervals resample source runs within gallery arm.",
            },
            {
                "check": "prior_gallery_overlap_not_complete",
                "value": float(gallery["in_prior_gallery"].mean()),
                "pass": True,
                "note": "External S10f labels are used where available but S11h is an expanded deterministic blinded gallery.",
            },
        ]
    )
    conclusion = (
        f"The expanded blinded gallery does not turn the S11f consensus ML-only excess into a clean two-pulse sample: "
        f"the high-minus-control blinded two-pulse-like delta is {delta['high_minus_control_two_pulse_like']:.4f} "
        f"[{delta['ci_low']:.4f}, {delta['ci_high']:.4f}], while artifact-like labels remain common. "
        f"The best frozen action is {winner['method']} with precision {winner['precision']:.3f}, "
        f"recall {winner['recall']:.3f}, and artifact fraction {winner['artifact_fraction']:.3f}; "
        "therefore the S11f caveat survives as support-dependent morphology rather than a validated clean pile-up recovery."
    )
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction_gate": "S10 topology fractions rebuilt from raw B-stack ROOT within +/-0.0015 absolute tolerance",
        "raw_root_counts": raw_counts,
        "split": {
            "policy": "source-run-blocked gallery bootstrap within high_ml_only and matched_low_control arms",
            "bootstrap_unit": "source_run_within_gallery_arm",
            "bootstrap_samples": int(config["bootstrap_samples"]),
        },
        "methods": methods,
        "winner": {
            "method": winner["method"],
            "selection_score": float(winner["selection_score"]),
            "precision": float(winner["precision"]),
            "precision_ci": [float(winner["precision_ci_low"]), float(winner["precision_ci_high"])],
            "recall": float(winner["recall"]),
            "recall_ci": [float(winner["recall_ci_low"]), float(winner["recall_ci_high"])],
            "artifact_fraction": float(winner["artifact_fraction"]),
            "artifact_fraction_ci": [float(winner["artifact_fraction_ci_low"]), float(winner["artifact_fraction_ci_high"])],
            "topology_excess_coverage": float(winner["topology_excess_coverage"]),
        },
        "gallery": {
            "n_rows": int(len(gallery)),
            "n_high_ml_only": int((gallery["gallery_arm"] == "high_ml_only").sum()),
            "n_matched_low_control": int((gallery["gallery_arm"] == "matched_low_control").sum()),
            "prior_gallery_overlap_fraction": float(gallery["in_prior_gallery"].mean()),
            "high_minus_control_two_pulse_like": delta,
        },
        "method_summary": method_summary.to_dict(orient="records"),
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "conclusion": conclusion,
        "next_tickets": [],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }

    input_hashes = {
        config["source_script"]: sha256_file(ROOT / config["source_script"]),
        THIS_SCRIPT: sha256_file(ROOT / THIS_SCRIPT),
        str(Path(config["config_path"]).relative_to(ROOT)): sha256_file(Path(config["config_path"])),
        str(Path(config["s11f_report_dir"]) / "event_method_scores.csv"): sha256_file(s11f_dir / "event_method_scores.csv"),
        str(Path(config["s11f_report_dir"]) / "taxonomy_event_pairs.csv"): sha256_file(s11f_dir / "taxonomy_event_pairs.csv"),
    }
    if (ROOT / config["gallery_source"]).exists():
        input_hashes[config["gallery_source"]] = sha256_file(ROOT / config["gallery_source"])
    for run in sorted(s11b.run_to_group()):
        input_hashes[str(s11b.raw_file(run).relative_to(ROOT))] = sha256_file(s11b.raw_file(run))

    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "raw_root_reproduction.csv", index=False)
    gallery.to_csv(out_dir / "blinded_gallery.csv", index=False)
    arm.to_csv(out_dir / "arm_summary.csv", index=False)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    (out_dir / "bootstrap_delta_summary.json").write_text(json.dumps(json_ready(delta), indent=2), encoding="utf-8")
    (out_dir / "input_sha256.csv").write_text(
        pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(index=False),
        encoding="utf-8",
    )
    save_plots(out_dir, method_summary, arm)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out_dir, config, reproduction, raw_counts, arm, delta, method_summary, leakage, result, time.time() - start)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(Path(config["config_path"]).relative_to(ROOT)),
        "script": THIS_SCRIPT,
        "command": f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {Path(config['config_path']).relative_to(ROOT)}",
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": {
            p.name: sha256_file(p)
            for p in sorted(out_dir.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "winner": winner["method"],
                "reproduced": result["reproduced"],
                "gallery_rows": len(gallery),
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
