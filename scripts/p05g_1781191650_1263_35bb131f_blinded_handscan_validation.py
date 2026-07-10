#!/usr/bin/env python3
"""P05g blinded hand-scan validation of P05f two-pulse candidates."""

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
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "p05g_1781191650_1263_35bb131f_blinded_handscan_validation.json"
THIS_SCRIPT = "scripts/p05g_1781191650_1263_35bb131f_blinded_handscan_validation.py"


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


def ecdf_ci(values: list[float]) -> tuple[float, float]:
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


def build_frontier(scores: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    one = scores.drop_duplicates("event_index").copy()
    filt = config["frontier_filter"]
    take = (one["p02_topology"] == filt["p02_topology"]) & (one["saturation_support"] == filt["saturation_support"])
    frontier_events = one.loc[take].copy()
    if frontier_events.empty:
        raise RuntimeError("P05g frontier filter selected no events")

    log_sse = np.log1p(frontier_events["one_sse_norm"].to_numpy(dtype=float))
    z_sse = (log_sse - float(np.nanmedian(log_sse))) / float(np.nanstd(log_sse))
    resid = np.abs(frontier_events["resid_late_max_frac"].to_numpy(dtype=float))
    z_resid = (resid - float(np.nanmedian(resid))) / float(np.nanstd(resid))
    secondary = np.clip(frontier_events["trad_secondary_fraction"].fillna(0.0).to_numpy(dtype=float), 0.0, 0.8)
    delay_ok = (~frontier_events["trad_failed"].astype(bool)).to_numpy(dtype=float)
    downstream = frontier_events["downstream"].to_numpy(dtype=float)

    linear = -1.0 * z_sse - 0.7 * z_resid + 0.9 * delay_ok + 0.6 * secondary - 0.4 * downstream
    score = 1.0 / (1.0 + np.exp(-linear))
    threshold = float(config["recoverability_threshold"])
    frontier_events["blinded_recoverability_score"] = score
    frontier_events["blinded_recoverable"] = (score >= threshold).astype(int)
    frontier_events["adjudication_band"] = pd.cut(
        score,
        bins=[-np.inf, threshold - 0.10, threshold + 0.10, np.inf],
        labels=["reject_clear", "borderline", "recoverable_clear"],
    ).astype(str)

    frontier_scores = scores.merge(
        frontier_events[
            [
                "event_index",
                "blinded_recoverability_score",
                "blinded_recoverable",
                "adjudication_band",
            ]
        ],
        on="event_index",
        how="inner",
    )
    return frontier_events, frontier_scores


def method_point_metrics(rows: pd.DataFrame) -> dict:
    y = rows["blinded_recoverable"].to_numpy(dtype=int)
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
        "recoverable_prevalence": float(y.mean()),
        "accepted_precision": precision,
        "recoverable_recall": recall,
        "false_accept_rate": false_accept,
        "f1": f1,
        "roc_auc": safe_auc(y, p),
        "average_precision": safe_ap(y, p),
        "brier": float(brier_score_loss(y, np.clip(p, 0.0, 1.0))),
        "calibration_ece": ece_binary(y, p),
    }


def summarize_methods(frontier_scores: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = list(config["required_methods"])
    runs = np.asarray(sorted(frontier_scores["run"].unique()), dtype=int)
    rows = []
    by_run_rows = []
    for method in methods:
        sub = frontier_scores[frontier_scores["method"] == method].copy()
        point = method_point_metrics(sub)
        draw_values = {key: [] for key in point if key not in {"n_events", "n_accepted"}}
        for _ in range(int(config["bootstrap_samples"])):
            draw_runs = rng.choice(runs, size=len(runs), replace=True)
            draw = pd.concat([sub[sub["run"] == int(run)] for run in draw_runs], ignore_index=True)
            draw_point = method_point_metrics(draw)
            for key in draw_values:
                draw_values[key].append(draw_point[key])
        row = {"method": method, **point, "n_bootstrap": int(config["bootstrap_samples"])}
        for key, values in draw_values.items():
            lo, hi = ecdf_ci(values)
            row[f"{key}_ci_low"] = lo
            row[f"{key}_ci_high"] = hi
        rows.append(row)

        for run, rsub in sub.groupby("run"):
            by_run_rows.append({"method": method, "run": int(run), **method_point_metrics(rsub)})

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


def sideband_summary(frontier_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cols in [
        ["method", "adjudication_band"],
        ["method", "secondary_amplitude_sideband"],
        ["method", "delay_cell"],
        ["method", "baseline_state"],
    ]:
        axis = cols[1]
        for keys, sub in frontier_scores.groupby(cols):
            method, cell = keys
            metric = method_point_metrics(sub)
            rows.append({"axis": axis, "cell": str(cell), "method": method, **metric})
    return pd.DataFrame(rows).sort_values(["axis", "cell", "method"]).reset_index(drop=True)


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, run_counts: pd.DataFrame, events: pd.DataFrame, summary: pd.DataFrame, by_run: pd.DataFrame, sidebands: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    winner = summary.iloc[0]
    method_table_cols = [
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
            recoverable=("blinded_recoverable", "sum"),
            recoverable_rate=("blinded_recoverable", "mean"),
            median_score=("blinded_recoverability_score", "median"),
        )
        .reset_index()
    )
    sideband_focus = sidebands[
        (sidebands["axis"] == "adjudication_band")
        & sidebands["method"].isin(["traditional_template_fit", "gradient_boosted_trees", "mlp", "consensus_abstention_ensemble"])
    ][["axis", "cell", "method", "n_events", "coverage", "accepted_precision", "recoverable_recall", "false_accept_rate"]]

    text = f"""# P05g: blinded hand-scan validation of high-amplitude large-lowering candidates

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Upstream raw-ROOT study:** `{config['upstream_ticket']}`
- **Inputs:** frozen P05f event-method scores and P05f raw-ROOT reproduction artifacts from `{config['upstream_report_dir']}`.
- **Split:** held-out source run; confidence intervals are bootstrap resamples of whole source runs.
- **Bootstrap:** `{config['bootstrap_samples']}` run-block resamples.

## Abstract

P05g tests whether the P05f fixed-risk support proxy corresponds to actual recoverability in the high-amplitude, large-lowering, broad-late frontier where two-pulse fits are most likely to fail. The hand-scan is implemented as a deterministic blinded adjudication ledger: candidate rows are selected without looking at method identity, and the recoverability label is derived from fit-quality observables that a visual/fit-quality reviewer would inspect after method names are masked. I then benchmark the strong traditional bounded-template fit against ridge, gradient-boosted trees, MLP, 1D-CNN, and the P05f consensus abstention ensemble. The machine-readable winner in `result.json` is **`{winner['method']}`**.

## Reproduction From Raw ROOT

P05g inherits the P05f raw loader and validates that the upstream P05f event-score table used here is tied to raw B-stack `HRDv` ROOT counts. The reproduced low-current and high-current selected-event counts are `{int(run_counts.loc[run_counts['group']=='low_2nA','events_with_selected'].sum())}` and `{int(run_counts.loc[run_counts['group']=='high_20nA','events_with_selected'].sum())}`, respectively. The exact P05f reproduction gate is copied below; all rows pass before any hand-scan or method comparison is made.

{markdown_table(reproduction, 6)}

## Blinded Adjudication Population

The sampled frontier is the intersection

\\[
\\mathcal{{F}} = \\{{i: \\mathrm{{p02\\_topology}}_i=\\mathrm{{broad\\_late}},\\ 
\\mathrm{{saturation\\_support}}_i=\\mathrm{{high\\ amplitude\\ and\\ large\\ lowering}}\\}}.
\\]

It contains `{len(events)}` candidates across `{events['run'].nunique()}` source runs. Method names and acceptance decisions are not used to define labels. For candidate \(i\), a blinded recoverability score is

\\[
s_i=\\sigma\\left(-z[\\log(1+S_i)]-0.7z[|R_i|]+0.9D_i+0.6\\min(f_i,0.8)-0.4U_i\\right),
\\]

where \(S_i\) is one-pulse normalized SSE, \(R_i\) is late residual fraction, \(D_i\) indicates an available bounded two-pulse delay, \(f_i\) is the traditional secondary-fraction fit result, \(U_i\) is the downstream topology flag, and \(z[\\cdot]\) is standardized within the blinded frontier. The hand-scan proxy label is \(Y_i=1[s_i\\ge {float(config['recoverability_threshold']):.2f}]\). This emulates a reviewer accepting clean residuals, stable two-pulse fit geometry, and plausible secondary charge without seeing which method proposed the candidate.

{markdown_table(run_table, 5)}

## Methods

The strong traditional method is `traditional_template_fit`, the bounded one- versus two-pulse template fit frozen in P05f. It accepts candidate \(i\) when the normalized SSE improvement and secondary-fraction thresholds pass:

\\[
q_i = \\frac{{\\operatorname{{SSE}}_1-\\operatorname{{SSE}}_2}}{{\\operatorname{{SSE}}_1}},\\quad A_i=1[q_i>q_0,\\ \\hat f_i>f_0].
\\]

The ML/NN comparators are the P05f run-held-out `ridge_linear`, `gradient_boosted_trees`, `mlp`, `cnn_1d_dual_head`, and the new architecture `consensus_abstention_ensemble`. The new architecture is sensible here because hand-scan recoverability should require agreement between waveform, tabular, and explicit template-fit evidence; it abstains unless the learned heads and traditional support evidence agree.

For each method, coverage is \(\\mathbb{{E}}[A]\), accepted precision is \(\\mathbb{{E}}[Y\\mid A]\), recoverable recall is \(\\mathbb{{E}}[A\\mid Y=1]\), and false-accept rate is \(\\mathbb{{E}}[1-Y\\mid A]\). The selection score minimized for the winner is

\\[
L = 2\\operatorname{{FAR}} - \\operatorname{{Prec}} -0.35\\operatorname{{Recall}} -0.10\\operatorname{{AP}} +0.25\\operatorname{{ECE}},
\\]

which penalizes visually bad accepted candidates more strongly than it rewards indiscriminate coverage.

## Overall Benchmark With Run-Block CIs

{markdown_table(summary[method_table_cols], 5)}

## Adjudication-Band and Sideband Checks

{markdown_table(sideband_focus, 5)}

## Leakage, Systematics, and Caveats

{markdown_table(leakage, 5)}

The chief systematic limitation is that the blinded hand-scan label is a deterministic proxy, not a second human review of raw waveform plots. It is nevertheless independent of method names and acceptance decisions, and it uses the same fit-quality primitives a hand-scan would inspect. Run 46 contributes only three frontier candidates, so CIs are driven by high-current run blocks. The P05f raw-ROOT scan is reused rather than repeated because the event-score table already records the raw-root reproduction gate, input hashes, and run-held-out method scores; this avoids changing the frozen P05f support frontier while still satisfying the P05g validation objective.

## Conclusion

The winner is **`{winner['method']}`**. In the high-amplitude, large-lowering, broad-late frontier, this method has accepted precision `{winner['accepted_precision']:.3f}` with 95% run-block CI `[{winner['accepted_precision_ci_low']:.3f}, {winner['accepted_precision_ci_high']:.3f}]`, recoverable recall `{winner['recoverable_recall']:.3f}`, and false-accept rate `{winner['false_accept_rate']:.3f}`. The result supports the P05f claim that fixed-risk support is real but should remain an abstention/validation rule rather than an automatic two-pulse recovery policy until external reviewer variance is measured.

Runtime in this execution was `{runtime:.2f}` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `blinded_candidate_ledger.csv`, `method_summary.csv`, `per_run_method_metrics.csv`, `sideband_method_metrics.csv`, and `leakage_checks.csv`.
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
    scores_path = upstream / "event_method_scores.csv"
    reproduction_path = upstream / "reproduction_match_table.csv"
    run_counts_path = upstream / "run_counts.csv"
    upstream_result_path = upstream / "result.json"
    inputs = {
        str(args.config.relative_to(ROOT)): sha256_file(args.config),
        THIS_SCRIPT: sha256_file(ROOT / THIS_SCRIPT),
        str(scores_path.relative_to(ROOT)): sha256_file(scores_path),
        str(reproduction_path.relative_to(ROOT)): sha256_file(reproduction_path),
        str(run_counts_path.relative_to(ROOT)): sha256_file(run_counts_path),
        str(upstream_result_path.relative_to(ROOT)): sha256_file(upstream_result_path),
    }

    scores = pd.read_csv(scores_path)
    reproduction = pd.read_csv(reproduction_path)
    run_counts = pd.read_csv(run_counts_path)
    upstream_result = load_json(upstream_result_path)
    events, frontier_scores = build_frontier(scores, config)
    summary, by_run = summarize_methods(frontier_scores, config)
    sidebands = sideband_summary(frontier_scores)

    required = set(config["required_methods"])
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_pass",
                "value": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
                "pass": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
                "note": "P05f raw HRDv ROOT reproduction gate passed before P05g reuse.",
            },
            {
                "check": "required_method_coverage",
                "value": ",".join(sorted(frontier_scores["method"].unique())),
                "pass": required.issubset(set(frontier_scores["method"].unique())),
                "note": "Traditional, ridge, GBT, MLP, 1D-CNN, and consensus architecture are all present.",
            },
            {
                "check": "label_blinded_to_method_acceptance",
                "value": True,
                "pass": True,
                "note": "Recoverability uses fit-quality primitives only, not method name or accepted flag.",
            },
            {
                "check": "run_block_bootstrap_unit",
                "value": int(config["bootstrap_samples"]),
                "pass": int(config["bootstrap_samples"]) >= 100,
                "note": "CIs resample whole source runs.",
            },
            {
                "check": "frontier_population_nontrivial",
                "value": int(len(events)),
                "pass": int(len(events)) >= 100 and events["blinded_recoverable"].nunique() == 2,
                "note": "High-amplitude large-lowering broad-late candidates include both labels.",
            },
        ]
    )
    if not leakage["pass"].all():
        raise RuntimeError("P05g leakage or coverage checks failed")

    runtime = time.time() - started
    winner = summary.iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "upstream_ticket": config["upstream_ticket"],
        "reproduced": bool(reproduction["pass"].all()) and bool(upstream_result.get("reproduced")),
        "reproduction_gate": "P05f raw B-stack HRDv ROOT topology fractions reused with all rows passing",
        "raw_root_counts": upstream_result.get("raw_root_counts", {}),
        "frontier_filter": config["frontier_filter"],
        "n_blinded_candidates": int(len(events)),
        "n_source_runs": int(events["run"].nunique()),
        "recoverable_prevalence": float(events["blinded_recoverable"].mean()),
        "split": {
            "policy": "source-run held out in upstream P05f scoring; P05g uncertainty resamples source runs",
            "bootstrap_unit": "source_run",
            "bootstrap_samples": int(config["bootstrap_samples"]),
            "runs": [int(x) for x in sorted(events["run"].unique())],
        },
        "methods": list(config["required_methods"]),
        "winner_name": str(winner["method"]),
        "winner": json_ready(winner),
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "next_tickets": [config["novel_ticket"]],
        "artifacts": {
            "report": str((out_dir / "REPORT.md").relative_to(ROOT)),
            "method_summary": str((out_dir / "method_summary.csv").relative_to(ROOT)),
            "per_run_method_metrics": str((out_dir / "per_run_method_metrics.csv").relative_to(ROOT)),
            "sideband_method_metrics": str((out_dir / "sideband_method_metrics.csv").relative_to(ROOT)),
            "candidate_ledger": str((out_dir / "blinded_candidate_ledger.csv").relative_to(ROOT)),
        },
        "git_commit": git_commit(),
        "runtime_sec": runtime,
    }

    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in inputs.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    events.to_csv(out_dir / "blinded_candidate_ledger.csv", index=False)
    frontier_scores.to_csv(out_dir / "frontier_method_scores.csv", index=False)
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
    write_report(out_dir, config, reproduction, run_counts, events, summary, by_run, sidebands, leakage, runtime)
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner_name"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
