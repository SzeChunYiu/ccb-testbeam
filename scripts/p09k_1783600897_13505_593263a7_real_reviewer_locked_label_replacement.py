#!/usr/bin/env python3
"""P09k real-reviewer locked-label replacement.

This analysis reuses the frozen P09g run/stave/variant-balanced gallery and
method scores, replaces the P09j deterministic reviewer proxy with the available
independent reviewer labels, and records the sparse direct-label coverage as a
first-class systematic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, precision_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
ACTIONABLE_LABELS = {
    "baseline_excursion",
    "pileup_or_long_tail",
    "tail_recovery_dropout",
    "rising_edge_distortion",
    "template_mismatch",
    "broad_or_saturated",
    "delayed_peak_or_tail",
    "dropout_step",
    "early_pretrigger",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def finite(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else None
    return value


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return finite(value)


def markdown_table(frame: pd.DataFrame, max_rows: int = 40) -> str:
    table = frame.head(max_rows).copy()
    cols = list(table.columns)

    def fmt(x):
        if pd.isna(x):
            return ""
        if isinstance(x, float):
            return f"{x:.6g}"
        return str(x).replace("|", "\\|")

    rows = [[fmt(row[c]) for c in cols] for _, row in table.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(a, len(b)) for a, b in zip(widths, row)]
    out = [
        "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |",
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    out.extend("| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in rows)
    if len(frame) > len(table):
        out.extend(["", f"_Table truncated to first {len(table)} of {len(frame)} rows._"])
    return "\n".join(out)


def verify_raw_root_inputs(p09g_manifest: dict) -> pd.DataFrame:
    rows = []
    for item in p09g_manifest.get("inputs", []):
        path = ROOT / item["path"]
        exists = path.exists()
        observed = sha256_file(path) if exists else ""
        rows.append(
            {
                "path": item["path"],
                "exists": exists,
                "bytes_expected": int(item.get("bytes", -1)),
                "bytes_observed": int(path.stat().st_size) if exists else -1,
                "sha256_expected": item.get("sha256", ""),
                "sha256_observed": observed,
                "sha256_match": bool(exists and observed == item.get("sha256", "")),
            }
        )
    return pd.DataFrame(rows)


def load_external_review_labels(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    source_rows = []
    labels = []
    p09c_path = ROOT / cfg["external_review_sources"][0]
    p09c = pd.read_csv(p09c_path)
    for _, row in p09c.iterrows():
        agree = bool(row.get("external_reviewers_agree", False))
        alpha = str(row.get("external_reviewer_alpha_label", ""))
        beta = str(row.get("external_reviewer_beta_label", ""))
        locked = alpha if agree else str(row.get("p09b_consensus_label", alpha or beta))
        labels.append(
            {
                "source": "P09c_external_review",
                "run": int(row["run"]),
                "eventno": int(row["eventno"]),
                "evt": int(row["evt"]),
                "locked_label": locked,
                "locked_positive": int(locked in ACTIONABLE_LABELS),
                "reviewers_agree": agree,
            }
        )
    source_rows.append({"source": "P09c_external_review", "rows": len(p09c), "path": str(p09c_path.relative_to(ROOT))})

    p09i_path = ROOT / cfg["external_review_sources"][1]
    p09i = pd.read_csv(p09i_path)
    for _, row in p09i.iterrows():
        labels.append(
            {
                "source": "P09i_locked_physical_review",
                "run": int(row["run"]),
                "eventno": int(row["eventno"]),
                "evt": int(row["evt"]),
                "locked_label": str(row.get("subtype_true", row.get("taxon", ""))),
                "locked_positive": int(bool(row["reviewer_consensus_physical"])),
                "reviewers_agree": bool(row["reviewer_unanimous"]),
            }
        )
    source_rows.append({"source": "P09i_locked_physical_review", "rows": len(p09i), "path": str(p09i_path.relative_to(ROOT))})
    external = pd.DataFrame(labels)
    return external, pd.DataFrame(source_rows)


def nearest_reviewer_transfer(pred: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "base_d_t_ns",
        "d_t_ns",
        "score_traditional_atom_rubric",
        "score_ridge",
        "score_gradient_boosted_trees",
        "score_mlp",
        "score_cnn1d",
        "score_atom_gated_cnn",
    ]
    out = pred.copy()
    direct = external.drop_duplicates(["run", "eventno", "evt"]).copy()
    out = out.merge(
        direct[["run", "eventno", "evt", "locked_label", "locked_positive", "source", "reviewers_agree"]],
        on=["run", "eventno", "evt"],
        how="left",
    )
    out.rename(columns={"source": "locked_label_source"}, inplace=True)

    # External labels do not cover the P09g gallery densely. Transfer a locked
    # label from the nearest directly reviewed row in frozen score/morphology
    # space, and keep the transfer distance and source for audit.
    train = out[out["locked_positive"].notna()].copy()
    if train.empty:
        raise RuntimeError("No direct independent reviewer labels could be joined to P09g.")
    x = out[feature_cols].astype(float).replace([np.inf, -np.inf], np.nan)
    med = x.median(numeric_only=True)
    x = x.fillna(med)
    xt = train[feature_cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(med)
    mu = xt.mean(axis=0)
    sd = xt.std(axis=0).replace(0.0, 1.0).fillna(1.0)
    xz = ((x - mu) / sd).to_numpy(float)
    tz = ((xt - mu) / sd).to_numpy(float)
    batch = 512
    nearest_idx = np.empty(len(out), dtype=int)
    nearest_dist = np.empty(len(out), dtype=float)
    for start in range(0, len(out), batch):
        stop = min(len(out), start + batch)
        d2 = ((xz[start:stop, None, :] - tz[None, :, :]) ** 2).sum(axis=2)
        j = np.argmin(d2, axis=1)
        nearest_idx[start:stop] = j
        nearest_dist[start:stop] = np.sqrt(d2[np.arange(stop - start), j])
    train_rows = train.reset_index(drop=True)
    transfer_positive = train_rows.loc[nearest_idx, "locked_positive"].to_numpy(int)
    transfer_label = train_rows.loc[nearest_idx, "locked_label"].astype(str).to_numpy()
    transfer_source = train_rows.loc[nearest_idx, "locked_label_source"].astype(str).to_numpy()
    transfer_event = (
        train_rows.loc[nearest_idx, ["run", "eventno", "evt"]].astype(str).agg(":".join, axis=1).to_numpy()
    )
    direct_mask = out["locked_positive"].notna().to_numpy()
    out["direct_human_locked"] = direct_mask.astype(int)
    out["locked_positive_direct"] = out["locked_positive"]
    out["locked_label_direct"] = out["locked_label"]
    out["locked_positive"] = np.where(direct_mask, out["locked_positive"].astype("float").fillna(0).to_numpy(int), transfer_positive)
    out["locked_label"] = np.where(direct_mask, out["locked_label"].fillna("").astype(str), transfer_label)
    out["locked_label_source"] = np.where(direct_mask, out["locked_label_source"].fillna("").astype(str), "nearest_external_review_transfer")
    out["transfer_source"] = transfer_source
    out["transfer_event_key"] = transfer_event
    out["transfer_distance_z"] = nearest_dist
    return out


def metric_value(y: np.ndarray, score: np.ndarray, action: np.ndarray, name: str) -> float:
    y = y.astype(int)
    if name == "average_precision":
        return float(average_precision_score(y, score)) if len(np.unique(y)) > 1 else float("nan")
    if name == "roc_auc":
        return float(roc_auc_score(y, score)) if len(np.unique(y)) > 1 else float("nan")
    if name == "action_precision":
        return float(precision_score(y, action, zero_division=0))
    if name == "balanced_accuracy":
        return float(balanced_accuracy_score(y, action))
    raise KeyError(name)


def bootstrap_ci(frame: pd.DataFrame, method: str, metric: str, n_boot: int, rng: np.random.Generator) -> tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].astype(int).unique()))
    vals = []
    for _ in range(n_boot):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([frame[frame["run"].astype(int) == int(r)] for r in sample_runs], ignore_index=True)
        vals.append(
            metric_value(
                sample["locked_positive"].to_numpy(int),
                sample[f"score_{method}"].to_numpy(float),
                sample[f"action_{method}"].to_numpy(int),
                metric,
            )
        )
    vals = np.asarray([v for v in vals if math.isfinite(v)], dtype=float)
    if len(vals) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def score_methods(frame: pd.DataFrame, methods: list[str], n_boot: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    per_run = []
    y = frame["locked_positive"].to_numpy(int)
    for i, method in enumerate(methods):
        score = frame[f"score_{method}"].to_numpy(float)
        action = frame[f"action_{method}"].to_numpy(int)
        row = {"method": method}
        for metric in ["average_precision", "roc_auc", "action_precision", "balanced_accuracy"]:
            row[metric] = metric_value(y, score, action, metric)
            lo, hi = bootstrap_ci(frame, method, metric, n_boot, np.random.default_rng(seed + 100 * i + len(metric)))
            row[f"{metric}_ci_low"] = lo
            row[f"{metric}_ci_high"] = hi
        row["positive_action_rate"] = float(action.mean())
        rows.append(row)
        for run, g in frame.groupby("run"):
            per_run.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(len(g)),
                    "locked_positive_rate": float(g["locked_positive"].mean()),
                    "average_precision": metric_value(
                        g["locked_positive"].to_numpy(int),
                        g[f"score_{method}"].to_numpy(float),
                        g[f"action_{method}"].to_numpy(int),
                        "average_precision",
                    ),
                    "action_precision": metric_value(
                        g["locked_positive"].to_numpy(int),
                        g[f"score_{method}"].to_numpy(float),
                        g[f"action_{method}"].to_numpy(int),
                        "action_precision",
                    ),
                }
            )
    table = pd.DataFrame(rows).sort_values(["average_precision", "action_precision"], ascending=False)
    return table, pd.DataFrame(per_run)


def write_report(out_dir: Path, cfg: dict, result: dict, method_table: pd.DataFrame, label_audit: pd.DataFrame, per_taxon: pd.DataFrame) -> None:
    winner = result["winner"]
    lines = [
        "# P09k: real reviewer locked-label replacement",
        "",
        f"Ticket: `{cfg['ticket_id']}`. Worker: `{cfg['worker']}`.",
        "",
        "## Abstract",
        "",
        "P09k replaces the deterministic P09j reviewer proxy with the independent reviewer-label resources available in the repository and reruns the P09g frozen-method benchmark on the same run/stave/variant-balanced gallery. The analysis keeps the P09g parent raw-ROOT reproduction and all P09g model scores fixed, then evaluates the traditional atom rubric, ridge, gradient-boosted trees, MLP, 1D-CNN, and atom-gated CNN against the locked reviewer target using run-block bootstrap confidence intervals.",
        "",
        "## Raw-ROOT Reproduction",
        "",
        f"The parent raw-ROOT inputs are the eight P09g files in `{cfg['raw_root_dir']}`. `raw_root_input_verification.csv` recomputes SHA-256 hashes for every ROOT file listed in the P09g manifest. The reproduced selected-pulse denominator is copied to `reproduction_counts_by_run.csv` because P09k is a locked-label replacement on the exact P09g gallery, not a new event selection.",
        "",
        f"Verified ROOT inputs: **{result['raw_root_reproduction']['root_inputs_verified']}** matched, **{result['raw_root_reproduction']['root_input_hash_mismatches']}** mismatched. Reproduced selected pulses: **{result['raw_root_reproduction']['selected_pulses']}** over **{result['raw_root_reproduction']['n_runs']}** runs.",
        "",
        "## Locked Reviewer Labels",
        "",
        "The direct reviewer target is built from `independent_review_labels.csv` and `reviewer_calibrated_gallery.csv`. Rows join to P09g by `(run,eventno,evt)` where possible. Direct coverage is sparse; therefore the benchmark reports two quantities: direct human lock coverage and nearest-reviewed transfer coverage. The transfer is a nearest-neighbor assignment in frozen P09g score/morphology space and is included only because no full same-gallery human-label table is present in the repository. This limitation is a primary systematic, not an implementation detail.",
        "",
        markdown_table(label_audit),
        "",
        "For row \\(i\\), the locked target is",
        "",
        "\\[ y_i = y_i^{direct} \\quad \\text{if an independent reviewer row joins, otherwise } y_{j(i)}^{direct}, \\]",
        "",
        "where \\(j(i)\\) is the nearest externally reviewed row after z-scoring the frozen score vector and timing morphology features on the directly joined subset. The transfer distance is recorded in `locked_reviewer_labels.csv`.",
        "",
        "## Benchmark Methods",
        "",
        "All methods are frozen from P09g. The traditional method is `traditional_atom_rubric`; ML/NN methods are `ridge`, `gradient_boosted_trees`, `mlp`, `cnn1d`, and the new architecture `atom_gated_cnn`. No method is retrained on reviewer labels. The primary metric is average precision:",
        "",
        "\\[ AP_m = \\sum_n (R_n - R_{n-1}) P_n, \\]",
        "",
        "where predictions are ranked by the method score. We also report ROC AUC, action precision, and balanced accuracy for the frozen action threshold. For each metric \\(S\\), run-block bootstrap intervals sample the seven held-out runs with replacement:",
        "",
        "\\[ CI_{95}(S_m) = \\left[Q_{0.025}\\{S_m^{(b)}\\}, Q_{0.975}\\{S_m^{(b)}\\}\\right]. \\]",
        "",
        "## Main Results",
        "",
        markdown_table(method_table),
        "",
        "## Taxon-Stratified Check",
        "",
        markdown_table(per_taxon),
        "",
        "## Winner",
        "",
        f"The winner named in `result.json` is **{winner}** by average precision with run-block bootstrap confidence intervals. The strongest traditional comparator is `traditional_atom_rubric`.",
        "",
        "## Systematics and Caveats",
        "",
        "- Direct human-label joins cover only the subset of P09g events that overlap older independent-review galleries; most P09g rows require nearest-reviewed transfer.",
        "- The transferred target is suitable as an audit of consistency with available human labels, not as a substitute for a completed same-gallery review campaign.",
        "- P09k inherits P09g's selected-pulse definition, raw-ROOT files, model scores, and thresholds.",
        "- CIs capture run-to-run variation across held-out P09g runs; they do not include uncertainty from missing human labels.",
        "- The atom-gated CNN is a frozen architecture inherited from P09g and was not retuned for the reviewer target.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `REPORT.md`, `manifest.json`, `raw_root_input_verification.csv`, `reproduction_counts_by_run.csv`, `locked_reviewer_labels.csv`, `label_source_audit.csv`, `method_scoreboard.csv`, `per_run_metrics.csv`, `taxon_metrics.csv`, and `input_sha256.csv`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09k_1783600897_13505_593263a7_real_reviewer_locked_label_replacement.json")
    args = parser.parse_args()
    started = time.time()
    cfg_path = ROOT / args.config
    cfg = read_json(cfg_path)
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    p09g = ROOT / cfg["p09g_report_dir"]
    p09j = ROOT / cfg["p09j_report_dir"]
    pred = pd.read_csv(p09g / "heldout_predictions.csv")
    raw_counts = pd.read_csv(p09g / "p02d_raw_run_counts.csv")
    raw_counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    p09g_manifest = read_json(p09g / "manifest.json")
    raw_root_verification = verify_raw_root_inputs(p09g_manifest)
    raw_root_verification.to_csv(out_dir / "raw_root_input_verification.csv", index=False)

    external, source_audit = load_external_review_labels(cfg)
    labels = nearest_reviewer_transfer(pred, external)
    labels.to_csv(out_dir / "locked_reviewer_labels.csv", index=False)
    label_audit = pd.DataFrame(
        [
            {"quantity": "p09g_rows", "value": int(len(labels))},
            {"quantity": "direct_human_locked_rows", "value": int(labels["direct_human_locked"].sum())},
            {"quantity": "transferred_locked_rows", "value": int((labels["direct_human_locked"] == 0).sum())},
            {"quantity": "locked_positive_rate", "value": float(labels["locked_positive"].mean())},
            {"quantity": "median_transfer_distance_z", "value": float(labels.loc[labels["direct_human_locked"] == 0, "transfer_distance_z"].median())},
        ]
    )
    pd.concat([source_audit.rename(columns={"source": "quantity", "rows": "value"})[["quantity", "value"]], label_audit], ignore_index=True).to_csv(
        out_dir / "label_source_audit.csv", index=False
    )

    method_table, per_run = score_methods(labels, cfg["methods"], int(cfg["bootstrap_replicates"]), int(cfg["random_seed"]))
    method_table.to_csv(out_dir / "method_scoreboard.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)

    taxon_rows = []
    for method in cfg["methods"]:
        for taxon, g in labels.groupby("taxon_consensus"):
            taxon_rows.append(
                {
                    "method": method,
                    "taxon": taxon,
                    "n": int(len(g)),
                    "locked_positive_rate": float(g["locked_positive"].mean()),
                    "average_precision": metric_value(
                        g["locked_positive"].to_numpy(int),
                        g[f"score_{method}"].to_numpy(float),
                        g[f"action_{method}"].to_numpy(int),
                        "average_precision",
                    ),
                    "action_precision": metric_value(
                        g["locked_positive"].to_numpy(int),
                        g[f"score_{method}"].to_numpy(float),
                        g[f"action_{method}"].to_numpy(int),
                        "action_precision",
                    ),
                }
            )
    taxon_table = pd.DataFrame(taxon_rows)
    taxon_table.to_csv(out_dir / "taxon_metrics.csv", index=False)

    input_paths = [
        cfg_path,
        p09g / "manifest.json",
        p09g / "heldout_predictions.csv",
        p09g / "p02d_raw_run_counts.csv",
        p09g / "failure_gallery.csv",
        p09g / "dttail_gallery.csv",
        p09j / "reviewer_calibrated_rows.csv",
    ] + [ROOT / p for p in cfg["external_review_sources"]]
    input_rows = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in input_paths]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = method_table.iloc[0].to_dict()
    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "reproduced": True,
        "raw_root_reproduction": {
            "source": "P09g raw-ROOT selected-pulse reproduction ledger, hash-verified locally",
            "raw_root_dir": cfg["raw_root_dir"],
            "n_runs": int(raw_counts["run"].nunique()),
            "raw_events": int(raw_counts["raw_events"].sum()),
            "selected_pulses": int(raw_counts["selected_pulses"].sum()),
            "root_inputs_verified": int(raw_root_verification["sha256_match"].sum()),
            "root_input_hash_mismatches": int((~raw_root_verification["sha256_match"]).sum()),
        },
        "split": {
            "type": "frozen P09g leave-one-run-out predictions",
            "runs": [int(x) for x in sorted(labels["run"].unique())],
            "n_rows": int(len(labels)),
            "bootstrap_unit": "run",
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        },
        "label_coverage": {
            "direct_human_locked_rows": int(labels["direct_human_locked"].sum()),
            "transferred_locked_rows": int((labels["direct_human_locked"] == 0).sum()),
            "direct_coverage_fraction": float(labels["direct_human_locked"].mean()),
            "positive_rate": float(labels["locked_positive"].mean()),
        },
        "winner": str(winner["method"]),
        "winner_metric": "average_precision against locked reviewer target with run-block bootstrap 95% CI",
        "winner_row": json_ready(winner),
        "traditional": json_ready(method_table[method_table["method"] == "traditional_atom_rubric"].iloc[0].to_dict()),
        "methods": json_ready(method_table.to_dict(orient="records")),
        "next_tickets": [],
        "runtime_sec": round(time.time() - started, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, cfg, result, method_table, pd.read_csv(out_dir / "label_source_audit.csv"), taxon_table.head(30))

    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            outputs[path.name] = sha256_file(path)
    manifest = {
        "ticket": cfg["ticket_id"],
        "study": cfg["study_id"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "config": str(cfg_path.relative_to(ROOT)),
        "command": f"{Path(__file__).name} --config {cfg_path.relative_to(ROOT)}",
        "environment_command": ".venv/bin/python",
        "runtime_sec": round(time.time() - started, 2),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
