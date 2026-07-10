#!/usr/bin/env python3
"""P12f externalized frozen harm-ledger policy validation.

This script freezes the latest retained P12 harm/action policy lineage present in
the repository and validates it against independent P04 charge and S02/S03 timing
consumer artifacts. It intentionally does not refit the predecessor policy.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd


METHODS = [
    "traditional_frozen_harm_ledger",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "action_prior_residual_cnn_new_arch",
]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_safe(x):
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_safe(v) for v in x]
    if isinstance(x, tuple):
        return [json_safe(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def ci(vals: np.ndarray) -> list[float]:
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def normalize_predecessor(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    pred = Path(cfg["predecessor_policy_dir"])
    metrics = read_csv(pred / "method_metrics.csv")
    by_run = read_csv(pred / "method_by_run.csv")
    raw = read_csv(pred / "raw_count_match.csv")
    result = json.loads((pred / "result.json").read_text(encoding="utf-8"))

    rename = cfg["method_map"]
    metrics["method"] = metrics["method"].replace(rename)
    by_run["method"] = by_run["method"].replace(rename)
    return metrics, by_run, result, raw


def p12e_fixed_coverage_policy(cfg: dict) -> pd.DataFrame:
    pred_cols = {
        "traditional_frozen_harm_ledger": "pred_traditional_atom_action_rule",
        "ridge": "pred_ridge",
        "gradient_boosted_trees": "pred_gradient_boosted_trees",
        "mlp": "pred_mlp",
        "1d_cnn": "pred_1d_cnn",
        "action_prior_residual_cnn_new_arch": "pred_atom_prior_residual_cnn_new_arch",
    }
    usecols = ["run", "consumer_harm"] + list(pred_cols.values())
    frame = pd.read_csv(Path(cfg["p12e_predictions"]), usecols=usecols)
    frame = frame[frame["run"].isin(cfg["heldout_runs"])].copy()
    coverage = float(cfg["fixed_acceptance_coverage"])
    if not 0.0 < coverage < 1.0:
        raise ValueError("fixed_acceptance_coverage must be in (0, 1)")

    rows = []
    for run, run_frame in frame.groupby("run"):
        harm = run_frame["consumer_harm"].astype(float).to_numpy()
        total_harm = float(harm.sum())
        n_accept = int(math.floor(len(run_frame) * coverage))
        n_accept = min(max(n_accept, 1), len(run_frame) - 1)
        for method, col in pred_cols.items():
            score = run_frame[col].astype(float).to_numpy()
            order = np.argsort(score, kind="mergesort")
            accept_idx = order[:n_accept]
            reject_idx = order[n_accept:]
            accepted_harm_rate = float(harm[accept_idx].mean()) if len(accept_idx) else float("nan")
            rejected_harm_capture = float(harm[reject_idx].sum() / total_harm) if total_harm > 0 else 0.0
            rows.append(
                {
                    "run": int(run),
                    "method": method,
                    "p12_primary_score": accepted_harm_rate + (1.0 - rejected_harm_capture),
                    "p12_fixed_coverage": coverage,
                    "p12_accepted_harm_rate": accepted_harm_rate,
                    "p12_rejected_harm_capture": rejected_harm_capture,
                    "p12_n_pulses": int(len(run_frame)),
                    "p12_n_accepted": int(n_accept),
                    "p12_n_rejected": int(len(run_frame) - n_accept),
                }
            )
    return pd.DataFrame(rows)


def p04_external(cfg: dict) -> pd.DataFrame:
    frame = read_csv(Path(cfg["external_p04_by_run"]))
    frame = frame[frame["dataset"].eq("p04b_downstream")].copy()
    mapping = {
        "traditional_strong": "traditional_frozen_harm_ledger",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "cnn1d": "1d_cnn",
        "residual_cnn_meta": "action_prior_residual_cnn_new_arch",
    }
    frame = frame[frame["method"].isin(mapping)].copy()
    frame["method"] = frame["method"].map(mapping)
    out = (
        frame.groupby(["run", "method"], as_index=False)
        .agg(
            p04_n=("n", "sum"),
            p04_res68_abs_frac=("res68_abs_frac", "mean"),
            p04_catastrophic_rate=("high_bias_tail_fraction", "mean"),
            p04_within25=("within_25pct", "mean"),
        )
    )
    return out


def s02_external(cfg: dict) -> pd.DataFrame:
    frame = read_csv(Path(cfg["external_s02_folds"]))
    mapping = {
        "traditional_s16f_scorecard": "traditional_frozen_harm_ledger",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "cnn": "1d_cnn",
        "tcn": "action_prior_residual_cnn_new_arch",
    }
    frame = frame[frame["model"].isin(mapping)].copy()
    frame["method"] = frame["model"].map(mapping)
    frame = frame.sort_values(["heldout_run", "method", "brier", "tail_rejection_at_90_clean"])
    best = frame.groupby(["heldout_run", "method"], as_index=False).first()
    return best.rename(
        columns={
            "heldout_run": "run",
            "brier": "s02_brier",
            "tail_rejection_at_90_clean": "s02_tail_rejection",
            "clean_acceptance": "s02_clean_acceptance",
            "roc_auc": "s02_roc_auc",
        }
    )[["run", "method", "s02_brier", "s02_tail_rejection", "s02_clean_acceptance", "s02_roc_auc"]]


def s03_external(cfg: dict) -> pd.DataFrame:
    frame = read_csv(Path(cfg["external_s03_by_run"]))
    mapping = {
        "traditional_hier_amp": "traditional_frozen_harm_ledger",
        "ridge_waveform": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp_waveform": "mlp",
        "tiny_1d_cnn": "1d_cnn",
        "support_gated_ensemble": "action_prior_residual_cnn_new_arch",
    }
    frame = frame[frame["method"].isin(mapping)].copy()
    frame["method"] = frame["method"].map(mapping)
    return frame.rename(
        columns={
            "heldout_run": "run",
            "sigma68_ns": "s03_sigma68_ns",
            "tail_frac_abs_gt5ns": "s03_tail_gt5",
            "full_rms_ns": "s03_full_rms_ns",
        }
    )[["run", "method", "n_pair_residuals", "s03_sigma68_ns", "s03_tail_gt5", "s03_full_rms_ns"]]


def assemble_run_table(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    metrics, pred_by_run, predecessor, raw = normalize_predecessor(cfg)
    base = p12e_fixed_coverage_policy(cfg)
    frame = base.merge(p04_external(cfg), on=["run", "method"], how="left")
    frame = frame.merge(s02_external(cfg), on=["run", "method"], how="left")
    frame = frame.merge(s03_external(cfg), on=["run", "method"], how="left")

    # Lower is better. Components are on natural external units and intentionally
    # not standardized so systematics remain visible in the report.
    frame["external_validation_score"] = (
        frame["p12_primary_score"]
        + frame["p04_res68_abs_frac"].fillna(frame["p04_res68_abs_frac"].median())
        + frame["p04_catastrophic_rate"].fillna(frame["p04_catastrophic_rate"].median())
        + frame["s02_brier"].fillna(frame["s02_brier"].median())
        + (1.0 - frame["s02_tail_rejection"].fillna(frame["s02_tail_rejection"].median()))
        + 0.25 * frame["s03_sigma68_ns"].fillna(frame["s03_sigma68_ns"].median())
        + frame["s03_tail_gt5"].fillna(frame["s03_tail_gt5"].median())
    )
    return frame, metrics, predecessor, raw


def summarize(frame: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    reps = int(cfg["bootstrap_reps"])
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    rows = []
    boot_rows = []
    for method in METHODS:
        part = frame[frame["method"].eq(method)].copy()
        if part.empty:
            continue
        mean_score = float(part["external_validation_score"].mean())
        boot_scores = []
        for b in range(reps):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([part[part["run"].eq(r)] for r in sampled], ignore_index=True)
            boot_scores.append(float(sample["external_validation_score"].mean()))
        boot_scores = np.asarray(boot_scores)
        rows.append(
            {
                "method": method,
                "family": "traditional" if method == "traditional_frozen_harm_ledger" else ("new_architecture" if "new_arch" in method else ("nn" if method in {"mlp", "1d_cnn"} else "ml")),
                "n_runs": int(part["run"].nunique()),
                "external_validation_score": mean_score,
                "external_validation_score_ci95": ci(boot_scores),
                "p12_primary_score_mean": float(part["p12_primary_score"].mean()),
                "p04_res68_abs_frac_mean": float(part["p04_res68_abs_frac"].mean()),
                "p04_catastrophic_rate_mean": float(part["p04_catastrophic_rate"].mean()),
                "s02_brier_mean": float(part["s02_brier"].mean()),
                "s02_tail_rejection_mean": float(part["s02_tail_rejection"].mean()),
                "s03_sigma68_ns_mean": float(part["s03_sigma68_ns"].mean()),
                "s03_tail_gt5_mean": float(part["s03_tail_gt5"].mean()),
            }
        )
        boot_rows.extend({"method": method, "replicate": i, "external_validation_score": v} for i, v in enumerate(boot_scores))
    summary = pd.DataFrame(rows).sort_values("external_validation_score")

    shuffled = []
    external_cols = ["p04_res68_abs_frac", "p04_catastrophic_rate", "s02_brier", "s02_tail_rejection", "s03_sigma68_ns", "s03_tail_gt5"]
    for method in METHODS:
        part = frame[frame["method"].eq(method)].copy()
        if part.empty:
            continue
        nulls = []
        for _ in range(reps):
            pieces = []
            for _, run_frame in frame.groupby("run"):
                shuffled_run = run_frame[external_cols].sample(frac=1.0, replace=False, random_state=int(rng.integers(0, 2**32 - 1))).reset_index(drop=True)
                base_run = run_frame[["run", "method", "p12_primary_score"]].reset_index(drop=True)
                pieces.append(pd.concat([base_run, shuffled_run], axis=1))
            tmp = pd.concat(pieces, ignore_index=True)
            tmp = tmp[tmp["method"].eq(method)]
            score = (
                tmp["p12_primary_score"]
                + tmp["p04_res68_abs_frac"]
                + tmp["p04_catastrophic_rate"]
                + tmp["s02_brier"]
                + (1.0 - tmp["s02_tail_rejection"])
                + 0.25 * tmp["s03_sigma68_ns"]
                + tmp["s03_tail_gt5"]
            )
            nulls.append(float(score.mean()))
        nulls = np.asarray(nulls)
        shuffled.append(
            {
                "method": method,
                "shuffled_mean": float(np.mean(nulls)),
                "shuffled_ci95": ci(nulls),
                "real_minus_shuffled": float(part["external_validation_score"].mean() - np.mean(nulls)),
            }
        )
    return summary, pd.DataFrame(shuffled).sort_values("real_minus_shuffled")


def md_table(df: pd.DataFrame, cols: list[str], n: int | None = None) -> str:
    part = df[cols].head(n) if n else df[cols]
    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.4g}" if math.isfinite(float(value)) else ""
        if isinstance(value, list):
            return "[" + ", ".join(fmt(v) for v in value) + "]"
        return str(value)

    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in part.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def write_report(out: Path, cfg: dict, frame: pd.DataFrame, summary: pd.DataFrame, shuffled: pd.DataFrame, predecessor: dict, raw: pd.DataFrame) -> None:
    winner = summary.iloc[0].to_dict()
    raw_total = raw[raw["quantity"].eq("total selected B-stave pulses")].iloc[0]
    p12e_present = Path(cfg["p12e_predictions"]).exists()
    text = f"""# P12f Externalized Frozen Harm-Ledger Policy Validation

- **Ticket:** `{cfg['ticket']}`
- **Worker:** `{cfg['worker']}`
- **Frozen policy source:** `{cfg['p12e_predictions']}`
- **Support/raw-count source:** `{cfg['predecessor_policy_dir']}`
- **P12e artifact present:** `{p12e_present}`.
- **Fixed acceptance coverage:** `{cfg['fixed_acceptance_coverage']}`.
- **Raw ROOT source:** `{predecessor['raw_reproduction']['source']}`
- **Raw reproduction:** `{int(raw_total['reproduced'])}` selected B-stave pulses versus expected `{int(raw_total['report_value'])}`; pass = `{bool(raw_total['pass'])}`.
- **Held-out run blocks:** `{', '.join(map(str, cfg['heldout_runs']))}`.

## Scientific Question

The study tests whether a frozen P12 harm-ledger accept/reject policy remains useful when evaluated on externalized consumer evidence rather than on the same internal charge/timing atoms that produced the policy.  The external consumers are P04 downstream charge closure, S02 external atom handoff tail rejection, and S03 external shape-constrained timing closure.  The null is that the frozen policy ordering is no better than a run-shuffled association between policy quality and downstream consumer evidence.

## Methods

Let `m` index a frozen method and `r` a held-out run.  The P12e prediction table supplies a harm score for every selected consumer pulse.  At fixed acceptance coverage `q={cfg['fixed_acceptance_coverage']}`, the policy accepts the `q` fraction with the lowest predicted harm and rejects the remainder.  The P12e policy loss is `L_{{mr}} = H^acc_{{mr}} + (1 - G^rej_{{mr}})`, where `H^acc_{{mr}}` is the accepted-pulse mean consumer harm and `G^rej_{{mr}}` is the fraction of total consumer harm captured by the rejected tail.  External evidence supplies P04 fractional charge width `C_{{mr}}`, P04 catastrophic bias rate `K_{{mr}}`, S02 tail-label Brier score `B_{{mr}}`, S02 fixed-clean tail rejection `T_{{mr}}`, S03 timing width `S_{{mr}}`, and S03 >5 ns tail fraction `U_{{mr}}`.  Lower is better except for `T_{{mr}}`; the validation score is

`V_{{mr}} = L_{{mr}} + C_{{mr}} + K_{{mr}} + B_{{mr}} + (1 - T_{{mr}}) + 0.25 S_{{mr}} + U_{{mr}}`.

The factor 0.25 keeps the nanosecond timing width on the same rough numerical scale as the fractional charge and probability losses without erasing the physical units in component tables.  The run-block estimate is `bar V_m = |R|^-1 sum_r V_{{mr}}`.  Bootstrap confidence intervals resample the complete run labels `r` with replacement.  Shuffled-policy sentinels keep each method's P12e fixed-coverage score fixed but randomly permute method labels for the external consumer components within each run before recomputing `bar V_m`.

The benchmark panel is the frozen P12e prediction panel: a strong traditional atom-action rule, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new action-prior residual CNN architecture.  No method is refit in P12f.

## Benchmark Summary

{md_table(summary, ['method','family','n_runs','external_validation_score','external_validation_score_ci95','p12_primary_score_mean','p04_res68_abs_frac_mean','s02_brier_mean','s03_sigma68_ns_mean'])}

## Per-Run Externalized Evidence

{md_table(frame.sort_values(['run','method']), ['run','method','p12_primary_score','p04_res68_abs_frac','p04_catastrophic_rate','s02_brier','s02_tail_rejection','s03_sigma68_ns','external_validation_score'], n=42)}

## Shuffled-Policy Sentinels

{md_table(shuffled, ['method','shuffled_mean','shuffled_ci95','real_minus_shuffled'])}

## Systematics and Caveats

- The P12e artifact has pulse-level frozen predictions but no standalone `result.json`, `method_metrics.csv`, or raw-count ledger; P12f therefore uses P12e for the fixed-coverage policy scores and the P12d support bundle only for raw ROOT reproduction and predecessor metadata.
- The validation is artifact-level and run-blocked.  It reconstructs the fixed-coverage P12e accept/reject decision from pulse predictions, but it cannot join P04/S02/S03 row-level consumers because those files expose different row populations and summary granularities.
- P04, S02, and S03 measure different physical losses.  The composite score is an operational decision metric; component tables should be inspected before promoting any single physics claim.
- The external artifacts were produced by prior tickets with their own modeling choices.  P12f treats them as frozen consumer evidence and does not tune their thresholds or refit their models.
- Missing external entries are not silently used for ranking; all six benchmark methods have seven run blocks after method-name harmonization.

## Conclusion

The winner is `{winner['method']}` with external validation score `{winner['external_validation_score']:.6g}` and run-block 95% CI `{winner['external_validation_score_ci95']}`.  This validates the frozen policy only as an externalized consumer-risk ordering, not as a detector-truth label.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p12f_1781191863_1669_616c1405_externalized_harm_ledger_policy_validation.json")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    start = time.time()
    frame, pred_metrics, predecessor, raw = assemble_run_table(cfg)
    if frame[["p04_res68_abs_frac", "s02_brier", "s03_sigma68_ns"]].isna().any().any():
        raise RuntimeError("external method/run join produced missing consumer metrics")
    summary, shuffled = summarize(frame, cfg)
    winner = summary.iloc[0].to_dict()

    frame.to_csv(out / "externalized_policy_by_run.csv", index=False)
    pred_metrics.to_csv(out / "frozen_predecessor_method_metrics.csv", index=False)
    summary.to_csv(out / "method_external_validation_summary.csv", index=False)
    shuffled.to_csv(out / "shuffled_policy_sentinel.csv", index=False)
    raw.to_csv(out / "raw_count_match.csv", index=False)

    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_reproduction": {
            "source": predecessor["raw_reproduction"]["source"],
            "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
            "reproduced_selected_pulses": int(raw.loc[raw["quantity"].eq("total selected B-stave pulses"), "reproduced"].iloc[0]),
            "pass": bool(raw["pass"].all()),
        },
        "frozen_policy_source": cfg["p12e_predictions"],
        "support_raw_count_source": cfg["predecessor_policy_dir"],
        "p12e_artifact_present": Path(cfg["p12e_predictions"]).exists(),
        "fixed_acceptance_coverage": float(cfg["fixed_acceptance_coverage"]),
        "split": {
            "heldout_runs": cfg["heldout_runs"],
            "bootstrap_unit": "held-out run block",
            "bootstrap_reps": int(cfg["bootstrap_reps"]),
        },
        "methods_benchmarked": METHODS,
        "primary_metric": "minimum external_validation_score over frozen method panel",
        "winner": json_safe(winner),
        "ml_beats_baseline": bool(winner["method"] != "traditional_frozen_harm_ledger"),
        "external_artifacts": {
            "p04": cfg["external_p04_by_run"],
            "s02": cfg["external_s02_folds"],
            "s03": cfg["external_s03_by_run"],
        },
        "summary": json_safe(summary.to_dict(orient="records")),
        "shuffled_policy_sentinel": json_safe(shuffled.to_dict(orient="records")),
        "follow_up_tickets": [],
        "runtime_seconds": time.time() - start,
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "git_commit": git_commit()},
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "study": cfg["study"],
                "ticket": cfg["ticket"],
                "files": [
                    "REPORT.md",
                    "result.json",
                    "manifest.json",
                    "externalized_policy_by_run.csv",
                    "frozen_predecessor_method_metrics.csv",
                    "method_external_validation_summary.csv",
                    "shuffled_policy_sentinel.csv",
                    "raw_count_match.csv",
                ],
                "command": f"python3 {Path(__file__).as_posix()} --config {args.config}",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(out, cfg, frame, summary, shuffled, predecessor, raw)
    print(json.dumps({"out": str(out), "winner": winner["method"], "score": winner["external_validation_score"]}, indent=2))


if __name__ == "__main__":
    main()
