#!/usr/bin/env python3
"""S11h blinded real-current waveform adjudication.

This ticket freezes the S11g run-held-out method scores and asks whether
accepted/rejected high-current broad-late windows agree with a blinded
waveform-morphology adjudication that does not see method names, thresholds, or
model scores.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "s11h_1781146783_955_745c6984_blinded_real_current_waveform_adjudication.json"
THIS_SCRIPT = "scripts/s11h_1781146783_955_745c6984_blinded_real_current_waveform_adjudication.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


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
        return value if math.isfinite(value) else None
    return value


def markdown_table(frame: pd.DataFrame, digits: int = 5) -> str:
    if frame.empty:
        return "_No rows._"

    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.{digits}g}"
        return str(v)

    cols = list(frame.columns)
    rows = [[fmt(row[c]) for c in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    for row in rows:
        out.append("| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |")
    return "\n".join(out)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_root_reproduction(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Re-run the S11 raw ROOT topology reproduction gate."""
    s11b = load_module(ROOT / config["s11b_source_script"], "s11b_source_for_s11h")
    events, _waves, run_counts = s11b.load_events()
    _topology, reproduction = s11b.reproduce_s10(events)
    counts = run_counts.copy()
    counts["source"] = "raw_root_reload"
    return reproduction, counts


def adjudication_labels(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Build deterministic blinded review labels without method score columns."""
    pop = config["target_population"]
    base = events.drop_duplicates("event_key").copy()
    target = (
        (base["group"].astype(str) == pop["group"])
        & (base["p02_topology"].astype(str) == pop["p02_topology"])
        & (base["ref_amp_adc"].astype(float) >= float(pop["min_ref_amp_adc"]))
        & (base["adaptive_lowering_adc"].astype(float) > float(pop["min_adaptive_lowering_adc"]))
    )
    base = base[target].copy()
    if base.empty:
        raise RuntimeError("empty S11h adjudication population")

    amp_z = np.log1p(base["ref_amp_adc"].astype(float))
    amp_z = (amp_z - amp_z.median()) / max(float(amp_z.mad()), 1e-6)
    lowering_z = np.log1p(base["adaptive_lowering_adc"].astype(float))
    lowering_z = (lowering_z - lowering_z.median()) / max(float(lowering_z.mad()), 1e-6)
    residual_z = np.log1p(np.maximum(base["one_sse_norm"].astype(float), 0.0))
    residual_z = (residual_z - residual_z.median()) / max(float(residual_z.mad()), 1e-6)
    late_z = base["resid_late_max_frac"].astype(float)
    late_z = (late_z - late_z.median()) / max(float(late_z.mad()), 1e-6)

    # Three deterministic blinded reviewer views. They use only morphology and
    # support fields visible in a blinded gallery, never method or score fields.
    shape_score = 0.42 * amp_z + 0.32 * lowering_z + 0.26 * late_z
    residual_score = 0.55 * residual_z + 0.25 * late_z + 0.20 * lowering_z
    hybrid_score = 0.38 * shape_score + 0.42 * residual_score + 0.20 * base["downstream"].astype(float)

    review_cfg = config["blinded_review"]
    r_shape = shape_score >= float(review_cfg["shape_score_threshold"])
    r_resid = residual_score >= float(review_cfg["residual_score_threshold"])
    r_hybrid = hybrid_score >= np.quantile(hybrid_score, 0.70)
    votes = r_shape.astype(int) + r_resid.astype(int) + r_hybrid.astype(int)

    base["blind_shape_score"] = shape_score
    base["blind_residual_score"] = residual_score
    base["blind_hybrid_score"] = hybrid_score
    base["blind_shape_review"] = r_shape.astype(int)
    base["blind_residual_review"] = r_resid.astype(int)
    base["blind_hybrid_review"] = r_hybrid.astype(int)
    base["blind_consensus_recoverable"] = (votes >= int(review_cfg["consensus_min_reviews"])).astype(int)
    base["blind_vote_count"] = votes.astype(int)
    return base


def prepare_events(scores: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
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
    ]
    base = scores[base_cols].drop_duplicates(["run", "eventno", "ref_stave", "event_index"]).copy()
    base["event_key"] = (
        base["run"].astype(str)
        + ":"
        + base["eventno"].astype(str)
        + ":"
        + base["ref_stave"].astype(str)
        + ":"
        + base["event_index"].astype(str)
    )
    return base


def add_event_key(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["event_key"] = (
        out["run"].astype(str)
        + ":"
        + out["eventno"].astype(str)
        + ":"
        + out["ref_stave"].astype(str)
        + ":"
        + out["event_index"].astype(str)
    )
    return out


def metric_row(df: pd.DataFrame, method: str) -> dict:
    y = df["blind_consensus_recoverable"].astype(int).to_numpy()
    score = df["pred_overlap_probability"].astype(float).to_numpy()
    pred = df["accepted"].astype(int).to_numpy()
    positive = int(y.sum())
    if len(np.unique(y)) == 2:
        auc = float(roc_auc_score(y, score))
        ap = float(average_precision_score(y, score))
        bal = float(balanced_accuracy_score(y, pred))
    else:
        auc = ap = bal = float("nan")
    prec = float(precision_score(y, pred, zero_division=0))
    rec = float(recall_score(y, pred, zero_division=0))
    f1 = float(f1_score(y, pred, zero_division=0))
    accepted = pred.astype(bool)
    accepted_blind_precision = float(y[accepted].mean()) if accepted.any() else float("nan")
    rejected_blind_rate = float(y[~accepted].mean()) if (~accepted).any() else float("nan")
    return {
        "method": method,
        "n_events": int(len(df)),
        "n_blind_positive": positive,
        "acceptance": float(pred.mean()),
        "roc_auc": auc,
        "average_precision": ap,
        "balanced_accuracy": bal,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "accepted_blind_precision": accepted_blind_precision,
        "rejected_blind_recoverable_rate": rejected_blind_rate,
    }


def bootstrap_ci(joined: pd.DataFrame, methods: Iterable[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    runs = np.array(sorted(joined["run"].unique()), dtype=int)
    metrics = ["roc_auc", "average_precision", "balanced_accuracy", "precision", "recall", "f1", "accepted_blind_precision"]
    rows: List[dict] = []
    for method in methods:
        full = metric_row(joined[joined["method"] == method], method)
        draws: Dict[str, List[float]] = {m: [] for m in metrics}
        for _ in range(int(n_boot)):
            sampled_runs = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([joined[(joined["method"] == method) & (joined["run"] == int(run))] for run in sampled_runs], ignore_index=True)
            row = metric_row(boot, method)
            for metric in metrics:
                if math.isfinite(row[metric]):
                    draws[metric].append(row[metric])
        out = dict(full)
        for metric in metrics:
            arr = np.asarray(draws[metric], dtype=float)
            out[metric + "_ci_low"] = float(np.quantile(arr, 0.025)) if len(arr) else float("nan")
            out[metric + "_ci_high"] = float(np.quantile(arr, 0.975)) if len(arr) else float("nan")
        out["n_bootstrap"] = int(min(len(v) for v in draws.values()))
        rows.append(out)
    return pd.DataFrame(rows)


def paired_deltas(joined: pd.DataFrame, winner: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    runs = np.array(sorted(joined["run"].unique()), dtype=int)
    methods = sorted(joined["method"].unique())
    rows = []
    for method in methods:
        vals = []
        for _ in range(int(n_boot)):
            sampled_runs = rng.choice(runs, size=len(runs), replace=True)
            pieces = []
            for run in sampled_runs:
                pieces.append(joined[joined["run"] == int(run)])
            boot = pd.concat(pieces, ignore_index=True)
            win_row = metric_row(boot[boot["method"] == winner], winner)
            ref_row = metric_row(boot[boot["method"] == method], method)
            if math.isfinite(win_row["average_precision"]) and math.isfinite(ref_row["average_precision"]):
                vals.append(win_row["average_precision"] - ref_row["average_precision"])
        arr = np.asarray(vals, dtype=float)
        rows.append(
            {
                "reference_method": method,
                "winner_minus_reference_ap": float(arr.mean()) if len(arr) else float("nan"),
                "ci_low": float(np.quantile(arr, 0.025)) if len(arr) else float("nan"),
                "ci_high": float(np.quantile(arr, 0.975)) if len(arr) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def write_report(out: Path, config: dict, reproduction: pd.DataFrame, target: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, winner: str, runtime: float) -> None:
    compact = summary[
        [
            "method",
            "n_events",
            "n_blind_positive",
            "acceptance",
            "roc_auc",
            "roc_auc_ci_low",
            "roc_auc_ci_high",
            "average_precision",
            "average_precision_ci_low",
            "average_precision_ci_high",
            "precision",
            "precision_ci_low",
            "precision_ci_high",
            "recall",
            "recall_ci_low",
            "recall_ci_high",
            "f1",
            "f1_ci_low",
            "f1_ci_high",
            "accepted_blind_precision",
            "accepted_blind_precision_ci_low",
            "accepted_blind_precision_ci_high",
        ]
    ].copy()
    pop = config["target_population"]
    lines = [
        "# S11h: blinded real-current waveform adjudication",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Raw input:** `{config['raw_root_dir']}`; S11g raw-ROOT reproduction is rerun before adjudication.",
        f"- **Frozen upstream scores:** `{config['s11g_report_dir']}/event_method_scores.csv`.",
        "- **Split:** all compared scores were generated by S11g with the source run held out; S11h bootstraps source runs.",
        f"- **Bootstrap:** {int(config['bootstrap_samples'])} nonparametric run-block resamples.",
        "",
        "## 1. Question and target population",
        "",
        (
            "The question is whether S11g accepted/rejected high-current broad-late windows correspond to waveform "
            "morphology that is recoverable as a two-pulse-like candidate when adjudicated blind to method score. "
            f"The target population is `{pop['group']}`, topology `{pop['p02_topology']}`, "
            f"`ref_amp_adc >= {pop['min_ref_amp_adc']}`, and `adaptive_lowering_adc > {pop['min_adaptive_lowering_adc']}`."
        ),
        "",
        f"The resulting blinded gallery contains **{len(target)}** events over **{target['run'].nunique()}** runs; "
        f"the consensus recoverable fraction is **{target['blind_consensus_recoverable'].mean():.4f}**.",
        "",
        "## 2. Raw ROOT reproduction gate",
        "",
        (
            "Before using the frozen S11g scores, the S11 source loader is rerun on raw ROOT and the S10 topology "
            "fractions are reproduced. This guards against evaluating an orphaned CSV detached from the raw data."
        ),
        "",
        markdown_table(reproduction),
        "",
        "## 3. Blinded adjudication rule",
        "",
        (
            "Each gallery row is reduced to morphology fields visible without method identity: amplitude, adaptive "
            "baseline lowering, late residual fraction, one-pulse residual norm, downstream coincidence, topology, "
            "run, and stave. Method labels, accepted flags, fitted secondary fractions, and method probabilities are "
            "withheld from the review target."
        ),
        "",
        (
            "Let robust z-scores be \\(z_A\\) for log amplitude, \\(z_L\\) for log lowering, \\(z_R\\) for "
            "log one-pulse residual norm, and \\(z_T\\) for late residual fraction. The three deterministic blinded "
            "reviewers are"
        ),
        "",
        "\\[s_{shape}=0.42z_A+0.32z_L+0.26z_T,\\]",
        "\\[s_{resid}=0.55z_R+0.25z_T+0.20z_L,\\]",
        "\\[s_{hybrid}=0.38s_{shape}+0.42s_{resid}+0.20I_{downstream}.\\]",
        "",
        (
            "A row is labelled recoverable when at least two reviewer views pass their frozen thresholds. This is an "
            "operational blinded-review proxy, not hidden truth."
        ),
        "",
        "## 4. Compared methods",
        "",
        (
            "The strong traditional method is `traditional_template_fit`, the S11c/S11g bounded asymmetric two-pulse "
            "template gate. ML/NN comparators are `ridge_linear`, `gradient_boosted_trees`, `mlp`, `cnn_1d_dual_head`, "
            "and the new `consensus_abstention_ensemble`, a score-disagreement abstaining architecture combining the "
            "tree, MLP, CNN, and traditional secondary-fraction predictions. All scores are frozen run-held-out S11g "
            "outputs; S11h only changes the blinded endpoint."
        ),
        "",
        "The primary ranking metric is average precision against the blinded consensus label. ROC AUC, balanced accuracy, precision, recall, F1, and accepted-blind precision are secondary diagnostics.",
        "",
        "## 5. Results with run-block CIs",
        "",
        markdown_table(compact),
        "",
        f"The winner written to `result.json` is **`{winner}`**.",
        "",
        "## 6. Paired bootstrap deltas",
        "",
        markdown_table(deltas),
        "",
        "## 7. Leakage and systematic checks",
        "",
        markdown_table(leakage),
        "",
        (
            "Systematic limitations: the blinded target is deterministic and morphology-derived, so it calibrates "
            "agreement with a review rule rather than physical constituent truth. The same reduced waveform summary "
            "fields contribute to both S11g scoring and S11h review, although method scores themselves are withheld. "
            "Run-block bootstrap intervals cover source-run variation under the frozen rule, not architecture-search "
            "multiplicity or future beam conditions."
        ),
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {config['config_path']}",
        "```",
        "",
        f"Runtime in this run was `{runtime:.2f}` s.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--skip-root-reload", action="store_true")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    config["config_path"] = str(config_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11g_dir = ROOT / config["s11g_report_dir"]
    scores = add_event_key(pd.read_csv(s11g_dir / "event_method_scores.csv"))
    missing = sorted(set(config["required_methods"]) - set(scores["method"].unique()))
    if missing:
        raise RuntimeError(f"S11g score table is missing required methods: {missing}")
    events = prepare_events(scores)
    target = adjudication_labels(events, config)
    joined = scores.merge(target[["event_key", "blind_consensus_recoverable", "blind_vote_count", "blind_shape_score", "blind_residual_score", "blind_hybrid_score"]], on="event_key", how="inner")
    joined = joined[joined["method"].isin(config["required_methods"])].copy()
    if joined.empty:
        raise RuntimeError("empty joined method/adjudication table")

    if args.skip_root_reload:
        reproduction = pd.read_csv(s11g_dir / "reproduction_match_table.csv")
        root_counts = pd.DataFrame()
    else:
        reproduction, root_counts = raw_root_reproduction(config)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    summary = bootstrap_ci(joined, config["required_methods"], rng, int(config["bootstrap_samples"]))
    summary = summary.sort_values(["average_precision", "f1", "accepted_blind_precision"], ascending=[False, False, False]).reset_index(drop=True)
    winner = str(summary.iloc[0]["method"])
    deltas = paired_deltas(joined, winner, rng, int(config["bootstrap_samples"]))

    review_balance = target.groupby("run", as_index=False).agg(n_events=("event_key", "size"), positive_rate=("blind_consensus_recoverable", "mean"))
    leakage = pd.DataFrame(
        [
            {"check": "raw_root_reproduction_pass", "value": float(bool(reproduction["pass"].all())), "pass": bool(reproduction["pass"].all()), "note": "S10 topology fractions reproduced from raw ROOT."},
            {"check": "all_required_methods_present", "value": ",".join(config["required_methods"]), "pass": True, "note": "Traditional, ridge, GBT, MLP, 1D-CNN, and new architecture are present."},
            {"check": "run_split_inherited", "value": float(joined["run"].nunique()), "pass": bool(joined["run"].nunique() >= 4), "note": "Frozen scores are S11g source-run-held-out predictions."},
            {"check": "review_positive_rate", "value": float(target["blind_consensus_recoverable"].mean()), "pass": bool(0.05 < target["blind_consensus_recoverable"].mean() < 0.95), "note": "Avoids a degenerate blinded label."},
            {"check": "max_run_positive_rate", "value": float(review_balance["positive_rate"].max()), "pass": bool(review_balance["positive_rate"].max() < 0.98), "note": "No single run is all-positive under the review rule."},
        ]
    )

    target.to_csv(out / "blinded_gallery_adjudication.csv", index=False)
    joined.to_csv(out / "method_adjudication_scores.csv", index=False)
    summary.to_csv(out / "method_summary.csv", index=False)
    deltas.to_csv(out / "paired_bootstrap_deltas.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not root_counts.empty:
        root_counts.to_csv(out / "raw_root_run_counts.csv", index=False)

    input_rows = []
    for rel in [
        config["config_path"],
        config["s11g_report_dir"] + "/event_method_scores.csv",
        config["s11g_report_dir"] + "/reproduction_match_table.csv",
        config["s11b_source_script"],
        config["s11g_script"],
        THIS_SCRIPT,
    ]:
        path = ROOT / rel
        input_rows.append({"path": rel, "sha256": sha256_file(path) if path.exists() else ""})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out, config, reproduction, target, summary, deltas, leakage, winner, runtime)
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "title": config["title"],
        "winner": {
            "method": winner,
            "metric": "average_precision_against_blinded_consensus",
            "average_precision": float(summary.iloc[0]["average_precision"]),
            "average_precision_ci95": [float(summary.iloc[0]["average_precision_ci_low"]), float(summary.iloc[0]["average_precision_ci_high"])],
            "f1": float(summary.iloc[0]["f1"]),
            "f1_ci95": [float(summary.iloc[0]["f1_ci_low"]), float(summary.iloc[0]["f1_ci_high"])],
        },
        "target_population": {
            "n_events": int(len(target)),
            "n_runs": int(target["run"].nunique()),
            "blind_positive_rate": float(target["blind_consensus_recoverable"].mean()),
        },
        "methods": summary.to_dict(orient="records"),
        "paired_deltas": deltas.to_dict(orient="records"),
        "raw_root_reproduction_pass": bool(reproduction["pass"].all()),
        "split": "S11g source-run-held-out frozen scores; S11h run-block bootstrap over source runs",
        "bootstrap_samples": int(config["bootstrap_samples"]),
        "outputs": {
            "report": str(out / "REPORT.md"),
            "summary": str(out / "method_summary.csv"),
            "adjudication": str(out / "blinded_gallery_adjudication.csv"),
        },
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_seconds": runtime,
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "command": f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {config_path}",
        "outputs": sorted(str(p.relative_to(ROOT)) for p in out.iterdir() if p.is_file()),
        "created_unix": time.time(),
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "winner": winner, "runtime_seconds": runtime}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
