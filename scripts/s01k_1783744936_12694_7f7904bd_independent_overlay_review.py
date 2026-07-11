#!/usr/bin/env python3
"""S01k independent overlay review feasibility and benchmark.

The claimed ticket asks for an independently reviewed overlay/real-current
gallery with at least 100 positives per labelled acquisition run. The available
independent S11h galleries are audited first; the benchmark is reported on the
largest compatible independent real-current review sample, while the positive
count gate is preserved as an explicit failing feasibility check.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = "scripts/s01k_1783744936_12694_7f7904bd_independent_overlay_review.py"
DEFAULT_CONFIG = "configs/s01k_1783744936_12694_7f7904bd_independent_overlay_review.yaml"


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(x):
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    return x


def import_s01j():
    path = ROOT / "scripts/s01j_1783605034_12126_04fe4a38_external_handscan_transfer.py"
    spec = importlib.util.spec_from_file_location("s01j_scan_for_s01k", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import S01j scan module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def safe_auc(y, s) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, s))


def safe_ap(y, s) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, s))


def bootstrap_ci(df: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> dict:
    runs = sorted(df["run"].unique())
    blocks = [
        (
            df.loc[df.run.eq(r), "y_true"].to_numpy(int),
            df.loc[df.run.eq(r), "score"].to_numpy(float),
            df.loc[df.run.eq(r), "accepted"].to_numpy(int),
        )
        for r in runs
    ]
    aucs, aps, f1s = [], [], []
    for _ in range(int(n_boot)):
        take = rng.integers(0, len(blocks), size=len(blocks))
        y = np.concatenate([blocks[i][0] for i in take])
        s = np.concatenate([blocks[i][1] for i in take])
        p = np.concatenate([blocks[i][2] for i in take])
        aucs.append(safe_auc(y, s))
        aps.append(safe_ap(y, s))
        f1s.append(float(f1_score(y, p, zero_division=0)))
    def q(vals, prob):
        vals = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
        return float(np.quantile(vals, prob)) if len(vals) else float("nan")
    return {
        "roc_auc_ci_low": q(aucs, 0.025),
        "roc_auc_ci_high": q(aucs, 0.975),
        "average_precision_ci_low": q(aps, 0.025),
        "average_precision_ci_high": q(aps, 0.975),
        "f1_ci_low": q(f1s, 0.025),
        "f1_ci_high": q(f1s, 0.975),
    }


def audit_positive_gate(df: pd.DataFrame, target_col: str, gate: int) -> pd.DataFrame:
    out = df.groupby("run").agg(
        n=("run", "size"),
        positives=(target_col, "sum"),
        positive_fraction=(target_col, "mean"),
    ).reset_index()
    out["required_positives"] = int(gate)
    out["pass"] = out["positives"] >= int(gate)
    return out


def secondary_gate_audit(path: str, gate: int) -> pd.DataFrame:
    df = pd.read_csv(path)
    candidates = []
    for col in df.columns:
        series = df[col].dropna()
        if len(series) and series.isin([0, 1, True, False]).all():
            by_run = df.groupby("run")[col].agg(["count", "sum"]).reset_index()
            candidates.append({
                "target_column": col,
                "n_runs": int(len(by_run)),
                "total_positive": int(by_run["sum"].sum()),
                "max_positive_in_run": int(by_run["sum"].max()),
                "runs_passing_100_positive_gate": int((by_run["sum"] >= gate).sum()),
            })
    return pd.DataFrame(candidates).sort_values(["runs_passing_100_positive_gate", "max_positive_in_run"], ascending=False)


def build_predictions(score_df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_col = config["target_column"]
    rows = []
    for method, meta in config["methods"].items():
        source_method = meta["source_method"]
        source = score_df.loc[score_df["method"].eq(source_method)].copy()
        if source.empty:
            raise RuntimeError(f"missing source method {source_method!r} for {method!r}")
        part = pd.DataFrame({
            "method": method,
            "source_method": source_method,
            "family": meta["family"],
            "run": source["run"].astype(int),
            "event_key": source["event_key"].astype(str),
            "y_true": source[target_col].astype(int),
            "score": source["pred_overlap_probability"].astype(float),
            "accepted": source["accepted"].astype(int),
            "accepted_secondary_contribution": source["accepted_secondary_contribution"].astype(float),
        })
        rows.append(part)
    pred = pd.concat(rows, ignore_index=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    summary_rows = []
    for (method, source_method, family), g in pred.groupby(["method", "source_method", "family"], sort=False):
        y = g["y_true"].to_numpy(int)
        score = g["score"].to_numpy(float)
        accepted = g["accepted"].to_numpy(int)
        ci = bootstrap_ci(g, int(config["bootstrap_samples"]), rng)
        summary_rows.append({
            "method": method,
            "source_method": source_method,
            "family": family,
            "n": int(len(g)),
            "positives": int(y.sum()),
            "roc_auc": safe_auc(y, score),
            "average_precision": safe_ap(y, score),
            "balanced_accuracy": float(balanced_accuracy_score(y, accepted)),
            "precision": float(precision_score(y, accepted, zero_division=0)),
            "recall": float(recall_score(y, accepted, zero_division=0)),
            "f1": float(f1_score(y, accepted, zero_division=0)),
            **ci,
        })
    summary = pd.DataFrame(summary_rows).sort_values(["average_precision", "roc_auc"], ascending=False)
    per_run = []
    for (method, run), g in pred.groupby(["method", "run"]):
        per_run.append({
            "method": method,
            "run": int(run),
            "n": int(len(g)),
            "positives": int(g["y_true"].sum()),
            "roc_auc": safe_auc(g["y_true"], g["score"]),
            "average_precision": safe_ap(g["y_true"], g["score"]),
            "f1": float(f1_score(g["y_true"], g["accepted"], zero_division=0)),
        })
    return pred, summary, pd.DataFrame(per_run)


def write_report(out_dir: Path, config: dict, result: dict, summary: pd.DataFrame, per_run: pd.DataFrame, repro: pd.DataFrame, gate: pd.DataFrame, secondary: pd.DataFrame) -> None:
    winner = result["winner"]
    top = summary.iloc[0]
    trad = summary.loc[summary["family"].eq("traditional")].iloc[0]
    lines = [
        "# S01k independent overlay review feasibility and benchmark",
        "",
        f"**Ticket:** `{config['ticket_id']}`  ",
        f"**Worker:** `{config['worker']}`  ",
        "**Date:** 2026-07-11",
        "",
        "## Abstract",
        "",
        "The ticket requested a repeat of S01j on an independently reviewed overlay/real-current gallery with at least 100 positive labels in every labelled acquisition run. I first audited the available independent S11h galleries and found that this positive-count gate is not satisfiable by the current artifacts: the largest compatible real-current adjudication has 986 rows over 12 runs, but the maximum positive count in any run is 28 for the consensus target.",
        "",
        f"The benchmark on the available independent real-current review sample is still reported using the frozen S11h method adjudication outputs. The named benchmark winner is **{winner}** with average precision **{top.average_precision:.4f}** [{top.average_precision_ci_low:.4f}, {top.average_precision_ci_high:.4f}] and ROC AUC **{top.roc_auc:.4f}** [{top.roc_auc_ci_low:.4f}, {top.roc_auc_ci_high:.4f}]. The strong traditional comparator is **{trad.method}** with AP **{trad.average_precision:.4f}** and ROC AUC **{trad.roc_auc:.4f}**. The result verdict is `{result['verdict']}` because the requested positive-count gate fails.",
        "",
        "## Raw ROOT Reproduction",
        "",
        repro.to_markdown(index=False),
        "",
        "The reproduction gate reruns the S01j raw ROOT scan before loading review labels. For each B-stack ROOT file, `HRDv` is pedestal-subtracted by the median of samples 0-3, reshaped into 8 channels by 18 samples, restricted to B2/B4/B6/B8 even channels, and counted when the baseline-subtracted maximum amplitude exceeds 1000 ADC. This exactly reproduces the established selected-pulse count of 640737.",
        "",
        "## Positive-Count Feasibility Gate",
        "",
        gate.to_markdown(index=False),
        "",
        "The explicit S01k gate requires at least 100 positives in every labelled run. Let \(n_r^+=\\sum_{i:r_i=r} y_i\). The gate is \(n_r^+ \\ge 100\\) for every labelled run \(r\). The current independent consensus target has \(\\max_r n_r^+=28\), so the requirement is empirically false for the available review table.",
        "",
        "Secondary target audit over the expanded S11h gallery:",
        "",
        secondary.head(20).to_markdown(index=False),
        "",
        "## Target and Split",
        "",
        f"The benchmark target is `{config['target_column']}` from `{config['label_path']}`. Scores and accept/reject decisions are loaded from `{config['method_score_path']}`. Rows are independent real-current waveform review rows from S11h, and the split unit is acquisition run. All intervals are nonparametric run-block bootstrap intervals: runs are sampled with replacement, all rows inside sampled runs are concatenated, and metrics are recomputed.",
        "",
        "For a method score \(s_m(x_i)\) and binary review label \(y_i\\in\\{0,1\\}\), ROC AUC is",
        "",
        "\\[\\mathrm{AUC}_m=P(s_m(x^+)>s_m(x^-))+\\tfrac{1}{2}P(s_m(x^+)=s_m(x^-)),\\]",
        "",
        "and average precision is the Riemann-Stieltjes sum over the precision-recall curve,",
        "",
        "\\[\\mathrm{AP}_m=\\sum_k (R_k-R_{k-1})P_k.\\]",
        "",
        "## Methods",
        "",
        "- **traditional_template_fit:** frozen transparent template-fit comparator, used as the strong traditional baseline.",
        "- **ridge:** display name for the frozen S11h `ridge_linear` method.",
        "- **gradient_boosted_trees:** frozen nonlinear tree ensemble method.",
        "- **mlp:** frozen multilayer perceptron comparator.",
        "- **1d_cnn:** display name for the frozen S11h `cnn_1d_dual_head` waveform network.",
        "- **consensus_abstention_ensemble_new:** display name for the frozen S11h `consensus_abstention_ensemble`; this is the new architecture slot because it combines method consensus with abstention rather than a single classifier.",
        "",
        "These are frozen method outputs, not newly trained waveform networks. This is intentional: the required high-positive independent training set does not exist, so retraining larger models would create a post-hoc model-selection artifact rather than a valid repeat of S01j.",
        "",
        "## Benchmark Table",
        "",
        summary.to_markdown(index=False),
        "",
        "## Per-Run Metrics",
        "",
        per_run.sort_values(["method", "run"]).to_markdown(index=False),
        "",
        "## Systematics and Caveats",
        "",
        "- The main requested feasibility condition fails; the benchmark is therefore diagnostic, not a completed adoption claim.",
        "- The target is deterministic blinded morphology review, not particle truth or human-labeled ground truth with 100 positives per run.",
        "- The method panel uses frozen S11h adjudication outputs because the independent positive sample is too small for credible retraining.",
        "- Run-block bootstrap intervals are wide where some held-out runs contain few positives.",
        "- Q-template transfer cannot be claimed from this independent real-current table because it does not carry S01j q-template RMSE columns.",
        "",
        "## Verdict",
        "",
        f"`result.json` names **{winner}** as the available-sample winner and records `positive_gate_pass=false`. No novel follow-up ticket is appended from this worker, because S01j already appended S01k and the objective allows at most one novel ticket.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {SCRIPT_PATH} --config {DEFAULT_CONFIG}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    config = load_yaml(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    s01j = import_s01j()
    repro_counts, reproduced = s01j.scan_raw_counts(config)
    expected = int(config["expected_selected_pulses"])
    repro_match = pd.DataFrame([{
        "quantity": "selected B-stave pulses with amplitude >1000 ADC",
        "expected": expected,
        "reproduced": int(reproduced),
        "delta": int(reproduced - expected),
        "tolerance": 0,
        "pass": bool(reproduced == expected),
    }])
    if reproduced != expected:
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {expected}")

    labels = pd.read_csv(config["label_path"])
    target_col = config["target_column"]
    gate = audit_positive_gate(labels, target_col, int(config["positive_gate_per_run"]))
    secondary = secondary_gate_audit(config["secondary_label_path"], int(config["positive_gate_per_run"]))
    scores = pd.read_csv(config["method_score_path"])
    pred, summary, per_run = build_predictions(scores, config)
    winner = str(summary.iloc[0]["method"])
    verdict = "blocked_positive_count_gate_available_sample_benchmark_only"

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "winner": winner,
        "winner_family": str(summary.iloc[0]["family"]),
        "winner_metric": "average_precision",
        "verdict": verdict,
        "raw_reproduction_pass": True,
        "positive_gate_pass": bool(gate["pass"].all()),
        "positive_gate_required_per_run": int(config["positive_gate_per_run"]),
        "max_positive_in_labelled_run": int(gate["positives"].max()),
        "reproduction_match_table": repro_match.to_dict(orient="records"),
        "n_labelled": int(len(labels)),
        "n_scored_events_per_method": int(pred.groupby("method")["event_key"].nunique().min()),
        "label_runs": [int(x) for x in sorted(labels["run"].unique())],
        "n_positive": int(labels[target_col].sum()),
        "method_summary": summary.to_dict(orient="records"),
        "novel_tickets": [],
        "runtime_seconds": float(time.time() - t0),
    }

    repro_counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    gate.to_csv(out_dir / "positive_gate_by_run.csv", index=False)
    secondary.to_csv(out_dir / "secondary_target_positive_gate_audit.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")
    input_rows = [
        {"path": args.config, "sha256": sha256_file(args.config)},
        {"path": SCRIPT_PATH, "sha256": sha256_file(SCRIPT_PATH)},
        {"path": config["label_path"], "sha256": sha256_file(config["label_path"])},
        {"path": config["method_score_path"], "sha256": sha256_file(config["method_score_path"])},
        {"path": config["secondary_label_path"], "sha256": sha256_file(config["secondary_label_path"])},
    ]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    write_report(out_dir, config, result, summary, per_run, repro_match, gate, secondary)
    manifest = {
        "ticket_id": config["ticket_id"],
        "config": args.config,
        "command": f"/home/billy/anaconda3/bin/python {SCRIPT_PATH} --config {args.config}",
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "outputs": sorted(str(p) for p in out_dir.iterdir() if p.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
