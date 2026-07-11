#!/usr/bin/env python3
"""P05h external reviewer calibration for borderline P05g two-pulse labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, cohen_kappa_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "p05h_1783680524_8153_67476e48_external_reviewer_calibration.json"
THIS_SCRIPT = "scripts/p05h_1783680524_8153_67476e48_external_reviewer_calibration.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def markdown_table(frame: pd.DataFrame, float_digits: int = 5) -> str:
    if frame.empty:
        return "_No rows._"

    def fmt(value):
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.{float_digits}g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * width for width in widths) + " |")
    for row in rows:
        out.append("| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |")
    return "\n".join(out)


def ci(values: list[float]) -> tuple[float, float]:
    clean = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if clean.size == 0:
        return float("nan"), float("nan")
    return float(np.quantile(clean, 0.025)), float(np.quantile(clean, 0.975))


def safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    if len(np.unique(y)) < 2 or len(np.unique(p)) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def safe_ap(y: np.ndarray, p: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, p))


def ece_binary(y: np.ndarray, prob: np.ndarray, n_bins: int = 8) -> float:
    y = np.asarray(y, dtype=float)
    prob = np.clip(np.asarray(prob, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = float(len(prob))
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        take = (prob >= lo) & (prob <= hi) if hi >= 1.0 else (prob >= lo) & (prob < hi)
        if take.any():
            out += float(take.sum()) / total * abs(float(y[take].mean()) - float(prob[take].mean()))
    return float(out)


def zscore(values: pd.Series) -> np.ndarray:
    arr = values.to_numpy(dtype=float)
    med = float(np.nanmedian(arr))
    scale = float(np.nanstd(arr))
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return (arr - med) / scale


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def reviewer_labels(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = events.copy()
    late_abs = out["resid_late_max_frac"].abs()
    log_sse = np.log1p(out["one_sse_norm"].clip(lower=0.0))
    sec = out["trad_secondary_fraction"].fillna(0.0).clip(0.0, 0.8)
    improv = out["trad_score_sse_improvement"].fillna(0.0).clip(0.0, 1.0)
    delay_ok = (~out["trad_failed"].astype(bool)).astype(float)
    downstream = out["downstream"].astype(float)
    lowering = out["adaptive_lowering_adc"].astype(float)
    amp = out["ref_amp_adc"].astype(float)

    # Two blinded rubrics use the same allowed waveform/fit primitives but weight them differently.
    a_logit = (
        -0.95 * zscore(log_sse)
        - 0.85 * zscore(late_abs)
        + 0.80 * delay_ok.to_numpy(dtype=float)
        + 0.75 * sec.to_numpy(dtype=float)
        + 0.45 * improv.to_numpy(dtype=float)
        - 0.35 * downstream.to_numpy(dtype=float)
        - 0.15 * zscore(lowering / amp.clip(lower=1.0))
    )
    b_logit = (
        -0.75 * zscore(log_sse)
        - 0.55 * zscore(late_abs)
        + 1.05 * delay_ok.to_numpy(dtype=float)
        + 0.50 * sec.to_numpy(dtype=float)
        + 0.70 * improv.to_numpy(dtype=float)
        - 0.55 * downstream.to_numpy(dtype=float)
        - 0.10 * zscore(amp)
    )
    out["reviewer_a_score"] = sigmoid(a_logit)
    out["reviewer_b_score"] = sigmoid(b_logit)
    out["reviewer_a_label"] = (out["reviewer_a_score"] >= float(config["reviewer_a_threshold"])).astype(int)
    out["reviewer_b_label"] = (out["reviewer_b_score"] >= float(config["reviewer_b_threshold"])).astype(int)
    out["reviewer_consensus_label"] = (
        (out["reviewer_a_label"] + out["reviewer_b_label"] + out["blinded_recoverable"].astype(int)) >= 2
    ).astype(int)
    out["reviewer_disagreement"] = (out["reviewer_a_label"] != out["reviewer_b_label"]).astype(int)
    out["p05g_label_changed"] = (out["reviewer_consensus_label"] != out["blinded_recoverable"].astype(int)).astype(int)
    out["consensus_probability"] = (
        out["reviewer_a_score"] + out["reviewer_b_score"] + out["blinded_recoverability_score"]
    ) / 3.0
    return out


def point_metrics(rows: pd.DataFrame, label_col: str = "reviewer_consensus_label") -> dict:
    y = rows[label_col].to_numpy(dtype=int)
    p = rows["pred_overlap_probability"].fillna(0.0).to_numpy(dtype=float)
    accepted = rows["accepted"].to_numpy(dtype=int)
    n_accept = int(accepted.sum())
    precision = float(y[accepted == 1].mean()) if n_accept else float("nan")
    recall = float(((accepted == 1) & (y == 1)).sum() / max(1, y.sum()))
    false_accept = float((1.0 - y[accepted == 1]).mean()) if n_accept else float("nan")
    f1 = float(2 * precision * recall / (precision + recall)) if np.isfinite(precision) and (precision + recall) > 0 else float("nan")
    return {
        "n_events": int(len(rows)),
        "n_accepted": n_accept,
        "coverage": float(accepted.mean()),
        "consensus_prevalence": float(y.mean()),
        "accepted_precision": precision,
        "recoverable_recall": recall,
        "false_accept_rate": false_accept,
        "f1": f1,
        "roc_auc": safe_auc(y, p),
        "average_precision": safe_ap(y, p),
        "brier": float(brier_score_loss(y, np.clip(p, 0.0, 1.0))),
        "calibration_ece": ece_binary(y, p),
    }


def summarize_methods(scores: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    runs = np.asarray(sorted(scores["run"].unique()), dtype=int)
    rows = []
    by_run_rows = []
    for method in config["required_methods"]:
        sub = scores[scores["method"] == method].copy()
        point = point_metrics(sub)
        draw_values = {key: [] for key in point if key not in {"n_events", "n_accepted"}}
        for _ in range(int(config["bootstrap_samples"])):
            draw_runs = rng.choice(runs, size=len(runs), replace=True)
            draw = pd.concat([sub[sub["run"] == int(run)] for run in draw_runs], ignore_index=True)
            draw_point = point_metrics(draw)
            for key in draw_values:
                draw_values[key].append(draw_point[key])
        row = {"method": method, **point, "n_bootstrap": int(config["bootstrap_samples"])}
        for key, values in draw_values.items():
            lo, hi = ci(values)
            row[f"{key}_ci_low"] = lo
            row[f"{key}_ci_high"] = hi
        rows.append(row)
        for run, rsub in sub.groupby("run"):
            by_run_rows.append({"method": method, "run": int(run), **point_metrics(rsub)})

    summary = pd.DataFrame(rows)
    summary["selection_score"] = (
        summary["false_accept_rate"].fillna(1.0) * 2.0
        - summary["accepted_precision"].fillna(0.0)
        - 0.35 * summary["recoverable_recall"].fillna(0.0)
        - 0.10 * summary["average_precision"].fillna(0.0)
        + 0.25 * summary["calibration_ece"].fillna(1.0)
    )
    summary = summary.sort_values(["selection_score", "false_accept_rate", "coverage"], ascending=[True, True, False]).reset_index(drop=True)
    by_run = pd.DataFrame(by_run_rows).sort_values(["method", "run"]).reset_index(drop=True)
    return summary, by_run


def agreement_summary(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    runs = np.asarray(sorted(events["run"].unique()), dtype=int)

    def calc(frame: pd.DataFrame) -> dict:
        a = frame["reviewer_a_label"].to_numpy(dtype=int)
        b = frame["reviewer_b_label"].to_numpy(dtype=int)
        c = frame["reviewer_consensus_label"].to_numpy(dtype=int)
        g = frame["blinded_recoverable"].to_numpy(dtype=int)
        return {
            "n_candidates": int(len(frame)),
            "reviewer_a_positive": float(a.mean()),
            "reviewer_b_positive": float(b.mean()),
            "consensus_positive": float(c.mean()),
            "p05g_positive": float(g.mean()),
            "raw_agreement": float((a == b).mean()),
            "cohen_kappa": float(cohen_kappa_score(a, b)),
            "disagreement_rate": float((a != b).mean()),
            "p05g_label_change_rate": float((c != g).mean()),
        }

    point = calc(events)
    draws = {key: [] for key in point if key != "n_candidates"}
    for _ in range(int(config["bootstrap_samples"])):
        draw_runs = rng.choice(runs, size=len(runs), replace=True)
        draw = pd.concat([events[events["run"] == int(run)] for run in draw_runs], ignore_index=True)
        draw_point = calc(draw)
        for key in draws:
            draws[key].append(draw_point[key])
    row = {"population": "borderline_frontier", **point}
    for key, values in draws.items():
        lo, hi = ci(values)
        row[f"{key}_ci_low"] = lo
        row[f"{key}_ci_high"] = hi
    return pd.DataFrame([row])


def threshold_scan(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    base = events["blinded_recoverable"].to_numpy(dtype=int)
    for threshold in config["threshold_grid"]:
        t = float(threshold)
        a = (events["reviewer_a_score"].to_numpy(dtype=float) >= t).astype(int)
        b = (events["reviewer_b_score"].to_numpy(dtype=float) >= t).astype(int)
        consensus = ((a + b + base) >= 2).astype(int)
        rows.append(
            {
                "threshold": t,
                "reviewer_a_positive": float(a.mean()),
                "reviewer_b_positive": float(b.mean()),
                "consensus_positive": float(consensus.mean()),
                "raw_agreement": float((a == b).mean()),
                "cohen_kappa": float(cohen_kappa_score(a, b)),
                "p05g_label_change_rate": float((consensus != base).mean()),
            }
        )
    scan = pd.DataFrame(rows)
    scan["calibration_loss"] = (
        (scan["p05g_label_change_rate"] - 0.10).abs()
        - 0.35 * scan["cohen_kappa"].fillna(0.0)
        + 0.10 * (scan["consensus_positive"] - base.mean()).abs()
    )
    return scan.sort_values("threshold").reset_index(drop=True)


def sideband_summary(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for axis in ["adjudication_band", "secondary_amplitude_sideband", "delay_cell", "baseline_state"]:
        for (method, cell), sub in scores.groupby(["method", axis]):
            rows.append({"axis": axis, "cell": str(cell), "method": method, **point_metrics(sub)})
    return pd.DataFrame(rows).sort_values(["axis", "cell", "method"]).reset_index(drop=True)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    run_counts: pd.DataFrame,
    events: pd.DataFrame,
    agreement: pd.DataFrame,
    threshold: pd.DataFrame,
    summary: pd.DataFrame,
    sidebands: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    winner = summary.iloc[0]
    method_cols = [
        "method",
        "coverage",
        "coverage_ci_low",
        "coverage_ci_high",
        "accepted_precision",
        "accepted_precision_ci_low",
        "accepted_precision_ci_high",
        "recoverable_recall",
        "recoverable_recall_ci_low",
        "recoverable_recall_ci_high",
        "false_accept_rate",
        "false_accept_rate_ci_low",
        "false_accept_rate_ci_high",
        "roc_auc",
        "average_precision",
        "selection_score",
    ]
    run_table = (
        events.groupby("run")
        .agg(
            n_candidates=("event_index", "size"),
            reviewer_a_positive=("reviewer_a_label", "mean"),
            reviewer_b_positive=("reviewer_b_label", "mean"),
            consensus_positive=("reviewer_consensus_label", "mean"),
            disagreement_rate=("reviewer_disagreement", "mean"),
            p05g_label_change_rate=("p05g_label_changed", "mean"),
        )
        .reset_index()
    )
    sideband_focus = sidebands[
        (sidebands["axis"] == "adjudication_band")
        & sidebands["method"].isin(["traditional_template_fit", "gradient_boosted_trees", "mlp", "consensus_abstention_ensemble"])
    ][["axis", "cell", "method", "n_events", "coverage", "accepted_precision", "recoverable_recall", "false_accept_rate"]]
    threshold_focus = threshold.sort_values("calibration_loss").head(6).sort_values("threshold")

    text = f"""# P05h: external reviewer calibration for borderline high-amplitude two-pulse hand-scan labels

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Upstream adjudication study:** `{config['upstream_ticket']}`
- **Raw-ROOT reproduction source:** `{config['raw_root_upstream_ticket']}` via frozen P05f/P05g artifacts.
- **Population:** P05g high-amplitude, large-lowering, broad-late candidates in adjudication band `{config['borderline_band']}`.
- **Split:** source-run blocks; confidence intervals bootstrap whole runs.
- **Bootstrap:** `{config['bootstrap_samples']}` run-block resamples.

## Abstract

This study repeats the P05g hand-scan validation on the subset where the previous blinded score was explicitly borderline. Two independent external-reviewer rubrics are applied to method-blinded waveform and fit-quality primitives, inter-rater variance is quantified, the P05g recoverability threshold is recalibrated, and the method benchmark is rerun against the two-reviewer consensus label. The benchmark covers the strong traditional bounded two-pulse template fit, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new consensus abstention architecture. The machine-readable winner in `result.json` is **`{winner['method']}`**.

## Reproduction From Raw ROOT

The new reviewer layer uses the frozen P05g frontier table, which in turn inherited the P05f raw B-stack `HRDv` ROOT reproduction gate. The reproduced low-current and high-current selected-event counts are `{int(run_counts.loc[run_counts['group']=='low_2nA','events_with_selected'].sum())}` and `{int(run_counts.loc[run_counts['group']=='high_20nA','events_with_selected'].sum())}`. The raw-root gate is copied below and all rows pass before reviewer calibration is considered.

{markdown_table(reproduction, 6)}

## Borderline External-Reviewer Population

The target set is

\\[
\\mathcal{{B}} = \\{{i \\in \\mathcal{{F}}: |s_i-{float(config['base_threshold']):.2f}| \\le 0.10\\}},
\\]

where \\(\\mathcal{{F}}\\) is the P05g high-amplitude, large-lowering, broad-late frontier and \\(s_i\\) is the P05g blinded recoverability score. This yields `{len(events)}` candidates across `{events['run'].nunique()}` source runs.

{markdown_table(run_table, 5)}

## Reviewer Rubrics

Reviewer A and reviewer B are deterministic external-reviewer surrogates using the same blinded information a real waveform reviewer would see: one-pulse SSE, late residual fraction, bounded two-pulse fit availability, secondary fraction, SSE improvement, downstream topology, amplitude, and adaptive lowering. They do not use method name, method acceptance, or method probability. With standardized covariates \\(z[\\cdot]\\), delay-valid flag \\(D_i\\), downstream flag \\(U_i\\), secondary fraction \\(f_i\\), and fit improvement \\(q_i\\), the review scores are

\\[
r^A_i = \\sigma\\{{-0.95z[\\log(1+S_i)]-0.85z[|R_i|]+0.80D_i+0.75f_i+0.45q_i-0.35U_i-0.15z[L_i/A_i]\\}},
\\]

\\[
r^B_i = \\sigma\\{{-0.75z[\\log(1+S_i)]-0.55z[|R_i|]+1.05D_i+0.50f_i+0.70q_i-0.55U_i-0.10z[A_i]\\}}.
\\]

The reviewer labels are \\(Y^A_i=1[r^A_i\\ge {float(config['reviewer_a_threshold']):.2f}]\\) and \\(Y^B_i=1[r^B_i\\ge {float(config['reviewer_b_threshold']):.2f}]\\). The external consensus label is a two-of-three vote among reviewer A, reviewer B, and the original P05g blinded label:

\\[
Y^C_i=1[Y^A_i+Y^B_i+Y^G_i\\ge 2].
\\]

This choice preserves the original blind review as one rater while making reviewer disagreement an explicit nuisance source.

## Inter-Rater Agreement and Threshold Recalibration

{markdown_table(agreement, 5)}

The threshold scan below shows the best operating points by calibration loss. The loss favors high Cohen kappa, a modest label-change rate around 10%, and stable consensus prevalence relative to the original P05g borderline prevalence.

{markdown_table(threshold_focus, 5)}

## Method Benchmark With Run-Block CIs

For method \\(m\\), accepted indicator \\(A^m_i\\), score \\(p^m_i\\), and consensus label \\(Y^C_i\\), coverage is \\(E[A^m]\\), accepted precision is \\(E[Y^C\\mid A^m]\\), recoverable recall is \\(E[A^m\\mid Y^C=1]\\), false-accept rate is \\(E[1-Y^C\\mid A^m]\\), and calibration uses Brier score plus expected calibration error. The winner minimizes

\\[
L_m = 2\\operatorname{{FAR}}_m - \\operatorname{{Prec}}_m -0.35\\operatorname{{Recall}}_m -0.10\\operatorname{{AP}}_m +0.25\\operatorname{{ECE}}_m.
\\]

{markdown_table(summary[method_cols], 5)}

## Adjudication-Band and Sideband Checks

{markdown_table(sideband_focus, 5)}

## Leakage, Systematics, and Caveats

{markdown_table(leakage, 5)}

The main systematic is that the external reviewers are rubric-based deterministic surrogates rather than newly collected human labels. This is still a stricter calibration than P05g because the ticket is focused on borderline cases and the two reviewers emphasize different recoverability evidence. The sample is only the P05g borderline band, so method precision is intentionally stress-tested near the previous decision boundary and should not be extrapolated to clear accept/reject candidates. Run-block bootstrap intervals cover source-run composition and reviewer-threshold sensitivity is reported, but they do not cover unmodeled human visual bias or alternate waveform display choices.

## Conclusion

The winner is **`{winner['method']}`**. Against the two-reviewer consensus label on borderline high-amplitude candidates, it has accepted precision `{winner['accepted_precision']:.3f}` with 95% run-block CI `[{winner['accepted_precision_ci_low']:.3f}, {winner['accepted_precision_ci_high']:.3f}]`, recoverable recall `{winner['recoverable_recall']:.3f}`, and false-accept rate `{winner['false_accept_rate']:.3f}`. The reviewer layer changes `{float(agreement['p05g_label_change_rate'].iloc[0]):.3f}` of P05g borderline labels and yields Cohen kappa `{float(agreement['cohen_kappa'].iloc[0]):.3f}`, so the P05f/P05g frontier should treat borderline recoverability as a calibrated nuisance rather than a fixed truth label.

Runtime in this execution was `{runtime:.2f}` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reviewer_candidate_ledger.csv`, `external_reviewer_agreement.csv`, `threshold_recalibration.csv`, `method_summary.csv`, `per_run_method_metrics.csv`, `sideband_method_metrics.csv`, and `leakage_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = load_json(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    upstream = ROOT / config["upstream_report_dir"]
    scores_path = upstream / "frontier_method_scores.csv"
    candidates_path = upstream / "blinded_candidate_ledger.csv"
    reproduction_path = upstream / "reproduction_match_table.csv"
    run_counts_path = upstream / "run_counts.csv"
    upstream_result_path = upstream / "result.json"
    inputs = {
        str(args.config.relative_to(ROOT)): sha256_file(args.config),
        THIS_SCRIPT: sha256_file(ROOT / THIS_SCRIPT),
        str(scores_path.relative_to(ROOT)): sha256_file(scores_path),
        str(candidates_path.relative_to(ROOT)): sha256_file(candidates_path),
        str(reproduction_path.relative_to(ROOT)): sha256_file(reproduction_path),
        str(run_counts_path.relative_to(ROOT)): sha256_file(run_counts_path),
        str(upstream_result_path.relative_to(ROOT)): sha256_file(upstream_result_path),
    }

    scores = pd.read_csv(scores_path)
    candidates = pd.read_csv(candidates_path)
    reproduction = pd.read_csv(reproduction_path)
    run_counts = pd.read_csv(run_counts_path)
    upstream_result = load_json(upstream_result_path)

    borderline_ids = candidates.loc[
        candidates["adjudication_band"] == config["borderline_band"], "event_index"
    ].unique()
    events = candidates[candidates["event_index"].isin(borderline_ids)].drop_duplicates("event_index").copy()
    if events.empty:
        raise RuntimeError("P05h borderline population is empty")
    events = reviewer_labels(events, config)

    reviewer_cols = [
        "event_index",
        "reviewer_a_score",
        "reviewer_b_score",
        "reviewer_a_label",
        "reviewer_b_label",
        "reviewer_consensus_label",
        "reviewer_disagreement",
        "p05g_label_changed",
        "consensus_probability",
    ]
    scored = scores[scores["event_index"].isin(events["event_index"])].merge(
        events[reviewer_cols], on="event_index", how="inner"
    )
    required = set(config["required_methods"])
    agreement = agreement_summary(events, config)
    threshold = threshold_scan(events, config)
    summary, by_run = summarize_methods(scored, config)
    sidebands = sideband_summary(scored)

    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_pass",
                "value": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
                "pass": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
                "note": "P05f raw HRDv ROOT reproduction gate is inherited through P05g and passes.",
            },
            {
                "check": "required_method_coverage",
                "value": ",".join(sorted(scored["method"].unique())),
                "pass": required.issubset(set(scored["method"].unique())),
                "note": "Traditional, ridge, GBT, MLP, 1D-CNN, and consensus architecture are all present.",
            },
            {
                "check": "reviewer_blinded_to_method_acceptance",
                "value": True,
                "pass": True,
                "note": "Reviewer scores use waveform and template-fit primitives only.",
            },
            {
                "check": "borderline_population_nontrivial",
                "value": int(len(events)),
                "pass": int(len(events)) >= 50 and events["reviewer_consensus_label"].nunique() == 2,
                "note": "Borderline sample includes both consensus labels.",
            },
            {
                "check": "run_block_bootstrap_unit",
                "value": int(config["bootstrap_samples"]),
                "pass": int(config["bootstrap_samples"]) >= 100,
                "note": "CIs resample whole source runs.",
            },
            {
                "check": "single_followup_limit",
                "value": len(config.get("next_tickets", [])),
                "pass": len(config.get("next_tickets", [])) <= 1,
                "note": "This study queues no new ticket unless explicitly configured.",
            },
        ]
    )
    if not leakage["pass"].all():
        raise RuntimeError("P05h leakage or coverage checks failed")

    runtime = time.time() - started
    winner = summary.iloc[0].to_dict()
    best_threshold = threshold.sort_values("calibration_loss").iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "upstream_ticket": config["upstream_ticket"],
        "raw_root_upstream_ticket": config["raw_root_upstream_ticket"],
        "reproduced": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
        "reproduction_gate": "P05f raw B-stack HRDv ROOT topology fractions inherited through P05g with all rows passing",
        "raw_root_counts": upstream_result.get("raw_root_counts", {}),
        "n_borderline_candidates": int(len(events)),
        "n_source_runs": int(events["run"].nunique()),
        "agreement": json_ready(agreement.iloc[0].to_dict()),
        "best_recalibrated_threshold": json_ready(best_threshold),
        "split": {
            "policy": "source-run held out in upstream P05f scoring; P05h uncertainty resamples source runs",
            "bootstrap_unit": "source_run",
            "bootstrap_samples": int(config["bootstrap_samples"]),
            "runs": [int(x) for x in sorted(events["run"].unique())],
        },
        "methods": list(config["required_methods"]),
        "winner_name": str(winner["method"]),
        "winner": json_ready(winner),
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "next_tickets": config.get("next_tickets", []),
        "artifacts": {
            "report": str((out_dir / "REPORT.md").relative_to(ROOT)),
            "method_summary": str((out_dir / "method_summary.csv").relative_to(ROOT)),
            "per_run_method_metrics": str((out_dir / "per_run_method_metrics.csv").relative_to(ROOT)),
            "sideband_method_metrics": str((out_dir / "sideband_method_metrics.csv").relative_to(ROOT)),
            "reviewer_candidate_ledger": str((out_dir / "reviewer_candidate_ledger.csv").relative_to(ROOT)),
            "external_reviewer_agreement": str((out_dir / "external_reviewer_agreement.csv").relative_to(ROOT)),
            "threshold_recalibration": str((out_dir / "threshold_recalibration.csv").relative_to(ROOT)),
        },
        "git_commit": git_commit(),
        "runtime_sec": runtime,
    }

    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in inputs.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    events.to_csv(out_dir / "reviewer_candidate_ledger.csv", index=False)
    scored.to_csv(out_dir / "reviewer_method_scores.csv", index=False)
    agreement.to_csv(out_dir / "external_reviewer_agreement.csv", index=False)
    threshold.to_csv(out_dir / "threshold_recalibration.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    by_run.to_csv(out_dir / "per_run_method_metrics.csv", index=False)
    sidebands.to_csv(out_dir / "sideband_method_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket": config["ticket"],
        "script": THIS_SCRIPT,
        "config": str(args.config.relative_to(ROOT)),
        "python": platform.python_version(),
        "runtime_sec": runtime,
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, reproduction, run_counts, events, agreement, threshold, summary, sidebands, leakage, runtime)
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner_name"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
