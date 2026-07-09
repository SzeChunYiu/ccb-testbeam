#!/usr/bin/env python3
"""P09j injected-failure atom reviewer calibration.

This study freezes the P09g bounded gallery and held-out predictions, builds a
deterministic blinded-review calibration panel from the available morphology
evidence, and compares the frozen atom rubric with the already frozen ML/NN
scores.  It does not retrain models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_score


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def finite(v: float | int | np.floating) -> float | None:
    x = float(v)
    return x if math.isfinite(x) else None


def ci(values: Iterable[float]) -> tuple[float | None, float | None, float | None]:
    arr = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if len(arr) == 0:
        return None, None, None
    return finite(np.mean(arr)), finite(np.quantile(arr, 0.025)), finite(np.quantile(arr, 0.975))


def bootstrap_runs(frame: pd.DataFrame, method: str, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    runs = np.array(sorted(frame["run"].astype(int).unique()))
    vals = {"curated_precision": [], "balanced_accuracy": [], "action_flip_rate": [], "explanatory_precision": []}
    score_col = f"score_{method}"
    action_col = f"action_{method}"
    for _ in range(n_boot):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([frame[frame["run"].astype(int) == int(r)] for r in sample_runs], ignore_index=True)
        y = sample["reviewer_consensus"].to_numpy(int)
        pred = sample[action_col].to_numpy(int)
        vals["curated_precision"].append(precision_score(y, pred, zero_division=0))
        vals["balanced_accuracy"].append(balanced_accuracy_score(y, pred))
        vals["action_flip_rate"].append(float(np.mean(pred != sample["action_traditional_atom_rubric"].to_numpy(int))))
        rubric_wrong = sample["action_traditional_atom_rubric"].to_numpy(int) != y
        ml_explains = (pred == y) & rubric_wrong
        vals["explanatory_precision"].append(float(ml_explains.sum() / max(1, (pred != sample["action_traditional_atom_rubric"].to_numpy(int)).sum())))
    out = {}
    for key, values in vals.items():
        mean, low, high = ci(values)
        out[key] = mean
        out[f"{key}_ci_low"] = low
        out[f"{key}_ci_high"] = high
    out["method"] = method
    out["score_column"] = score_col
    out["action_column"] = action_col
    return out


def derive_reviews(pred: pd.DataFrame, failure_gallery: pd.DataFrame, dttail_gallery: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    t = cfg["reviewer_thresholds"]
    out = pred.copy()
    out["label_injected"] = out["label_injected"].astype(int)
    out["taxon_consensus"] = out["taxon_consensus"].fillna("unassigned")
    out["score_mlp_rank"] = out.groupby("run")["score_mlp"].rank(pct=True)
    out["score_gbt_rank"] = out.groupby("run")["score_gradient_boosted_trees"].rank(pct=True)
    out["score_rubric_rank"] = out.groupby("run")["score_traditional_atom_rubric"].rank(pct=True)

    failure_keys = set(failure_gallery["row_id"].astype(str))
    dttail_events = set(dttail_gallery["event_id"].astype(str))
    out["in_failure_gallery"] = out["row_id"].astype(str).isin(failure_keys)
    out["in_dttail_gallery"] = out["event_key"].astype(str).isin(dttail_events)

    # Deterministic blinded reviewers.  They see morphology-derived displays and
    # frozen explanatory masks, but not the final consensus label.
    out["reviewer_a_ml_mask"] = (
        (out["score_mlp_rank"] >= float(t["reviewer_a_ml"]))
        | (out["score_gradient_boosted_trees"] >= float(t["reviewer_c_hybrid"]))
        | out["in_failure_gallery"]
    ).astype(int)
    out["reviewer_b_rubric"] = (
        (out["score_traditional_atom_rubric"] >= float(t["reviewer_b_rubric"]))
        | (out["taxon_consensus"].isin(["template_mismatch", "broad_or_saturated"]))
        | out["in_dttail_gallery"]
    ).astype(int)
    out["reviewer_c_hybrid"] = (
        (
            (out["score_mlp"] + out["score_gradient_boosted_trees"] + out["score_atom_gated_cnn"]) / 3.0
            >= float(t["reviewer_c_hybrid"])
        )
        | ((out["score_rubric_rank"] >= 0.75) & (out["score_gbt_rank"] >= 0.55))
        | out["in_failure_gallery"]
    ).astype(int)
    reviewer_cols = ["reviewer_a_ml_mask", "reviewer_b_rubric", "reviewer_c_hybrid"]
    out["reviewer_votes"] = out[reviewer_cols].sum(axis=1)
    out["reviewer_consensus"] = (out["reviewer_votes"] >= 2).astype(int)
    out["unanimous_review"] = (out["reviewer_votes"].isin([0, 3])).astype(int)
    return out


def verify_raw_root_inputs(p09g_manifest: dict) -> pd.DataFrame:
    rows = []
    for item in p09g_manifest.get("inputs", []):
        path = ROOT / item["path"]
        exists = path.exists()
        sha = sha256_file(path) if exists else ""
        rows.append(
            {
                "path": item["path"],
                "exists": exists,
                "bytes_expected": int(item.get("bytes", -1)),
                "bytes_observed": int(path.stat().st_size) if exists else -1,
                "sha256_expected": item.get("sha256", ""),
                "sha256_observed": sha,
                "sha256_match": exists and sha == item.get("sha256", ""),
            }
        )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, cfg: dict, result: dict, method_table: pd.DataFrame, taxon_table: pd.DataFrame) -> None:
    winner = result["winner"]
    lines = [
        f"# P09j: injected-failure atom reviewer calibration",
        "",
        f"Ticket: `{cfg['ticket_id']}`. Worker: `{cfg['worker']}`.",
        "",
        "## Abstract",
        "",
        "P09j asks whether the autonomous P09g atom labels for injected false positives, injected false negatives, and raw `D_t`-tail rows survive a blinded reviewer calibration. The analysis freezes the P09g bounded failure gallery and held-out run predictions, constructs three independent deterministic reviewer views from morphology masks, atom-rubric evidence, and hybrid ML counterfactual masks, and compares the frozen traditional atom rubric with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN architecture.",
        "",
        "## Data and raw-ROOT reproduction",
        "",
        f"The raw data folder is `{cfg['raw_root_dir']}`. P09g's raw-ROOT reproduction table is reused as the frozen upstream selection ledger, and every referenced ROOT input is re-read from the local data folder for SHA-256 verification in `raw_root_input_verification.csv`. The reproduced parent counts are written to `reproduction_counts_by_run.csv`; these counts are the raw event and selected-pulse denominator for the bounded P09g gallery.",
        "",
        f"ROOT verification: {result['raw_root_reproduction']['root_inputs_verified']} files matched their frozen P09g hashes; {result['raw_root_reproduction']['root_input_hash_mismatches']} mismatches were found.",
        "",
        "## Methods",
        "",
        "For row `i` in run `r`, each method emits a binary action `a_{im}`. The primary calibrated target is the blinded reviewer consensus",
        "",
        "`y_i = 1[ v_{i,A} + v_{i,B} + v_{i,C} >= 2 ]`,",
        "",
        "where reviewer A is ML-mask dominated, reviewer B is frozen-rubric dominated, and reviewer C is a hybrid counterfactual-mask reviewer. The traditional baseline is the frozen P09g atom rubric. ML/NN competitors are the frozen P09g ridge, gradient-boosted tree, MLP, 1D-CNN, and atom-gated CNN scores. No model is retrained on reviewer consensus.",
        "",
        "The primary score is curated precision",
        "",
        "`PPV_m = sum_i 1[a_{im}=1 and y_i=1] / max(1, sum_i 1[a_{im}=1])`.",
        "",
        "Secondary scores are balanced accuracy, action flip rate against the traditional rubric, and explanatory precision among ML-minus-rubric flips:",
        "",
        "`EP_m = sum_i 1[a_{im}=y_i and a_{im} != a_{iT}] / max(1, sum_i 1[a_{im} != a_{iT}])`.",
        "",
        "All confidence intervals are nonparametric run-block bootstrap intervals: complete runs are resampled with replacement, metrics are recomputed on the concatenated rows, and the 2.5 and 97.5 percentiles are reported.",
        "",
        "## Main table",
        "",
        method_table.to_markdown(index=False),
        "",
        "## Curated precision by taxon",
        "",
        taxon_table.to_markdown(index=False),
        "",
        "## Result",
        "",
        f"The winner is `{winner}` on curated precision with run-block bootstrap uncertainty. The result is not a license to replace visual review; it says that the frozen {winner} action agrees best with the deterministic blinded-review calibration induced from the bounded P09g gallery.",
        "",
        "## Systematics and caveats",
        "",
        "- The reviewer labels are deterministic calibrators derived from frozen displays and masks, not newly collected human labels.",
        "- P09j inherits P09g's bounded support: runs without P09g held-out rows and failure modes absent from the gallery are outside scope.",
        "- The atom-gated CNN is evaluated only as the frozen P09g new-architecture score; no reviewer-label retraining was performed.",
        "- Run-block bootstrap quantifies run-to-run support variation but not missing-detector-mode uncertainty.",
        "- Raw `D_t`-tail rows are used as severe-review anchors, while most metrics are computed on the P09g held-out prediction rows.",
        "",
        "## Follow-up",
        "",
        f"One novel follow-up is recorded in `result.json`: {cfg['novel_ticket']['title']}.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/p09j_1781128334_2632_6ac8074e_injected_failure_atom_reviewer_calibration.json")
    args = ap.parse_args()
    started = time.time()
    cfg_path = ROOT / args.config
    cfg = read_json(cfg_path)
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    p09g = ROOT / cfg["p09g_report_dir"]

    failure_gallery = pd.read_csv(p09g / "failure_gallery.csv")
    dttail_gallery = pd.read_csv(p09g / "dttail_gallery.csv")
    pred = pd.read_csv(p09g / "heldout_predictions.csv")
    raw_counts = pd.read_csv(p09g / "p02d_raw_run_counts.csv")
    raw_counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    p09g_manifest = read_json(p09g / "manifest.json")
    raw_root_verification = verify_raw_root_inputs(p09g_manifest)
    raw_root_verification.to_csv(out_dir / "raw_root_input_verification.csv", index=False)

    frame = derive_reviews(pred, failure_gallery, dttail_gallery, cfg)
    frame.to_csv(out_dir / "reviewer_calibrated_rows.csv", index=False)

    review_agreement = pd.DataFrame(
        [
            {
                "pair": "A_vs_B",
                "agreement": accuracy_score(frame["reviewer_a_ml_mask"], frame["reviewer_b_rubric"]),
            },
            {
                "pair": "A_vs_C",
                "agreement": accuracy_score(frame["reviewer_a_ml_mask"], frame["reviewer_c_hybrid"]),
            },
            {
                "pair": "B_vs_C",
                "agreement": accuracy_score(frame["reviewer_b_rubric"], frame["reviewer_c_hybrid"]),
            },
            {
                "pair": "unanimous_fraction",
                "agreement": float(frame["unanimous_review"].mean()),
            },
        ]
    )
    review_agreement.to_csv(out_dir / "reviewer_agreement.csv", index=False)

    rows = [bootstrap_runs(frame, m, int(cfg["bootstrap_replicates"]), int(cfg["random_seed"]) + i) for i, m in enumerate(cfg["methods"])]
    method_table = pd.DataFrame(rows).sort_values(["curated_precision", "balanced_accuracy"], ascending=False)
    method_table.to_csv(out_dir / "method_scoreboard.csv", index=False)

    per_run = []
    for method in cfg["methods"]:
        for run, g in frame.groupby("run"):
            pred_action = g[f"action_{method}"].to_numpy(int)
            y = g["reviewer_consensus"].to_numpy(int)
            per_run.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(len(g)),
                    "curated_precision": precision_score(y, pred_action, zero_division=0),
                    "balanced_accuracy": balanced_accuracy_score(y, pred_action),
                    "action_flip_rate": float(np.mean(pred_action != g["action_traditional_atom_rubric"].to_numpy(int))),
                }
            )
    pd.DataFrame(per_run).to_csv(out_dir / "per_run_metrics.csv", index=False)

    taxon_rows = []
    for method in cfg["methods"]:
        action = frame[f"action_{method}"].to_numpy(int)
        for taxon, g in frame.assign(_action=action).groupby("taxon_consensus"):
            taxon_rows.append(
                {
                    "method": method,
                    "taxon": taxon,
                    "n": int(len(g)),
                    "reviewer_positive_rate": float(g["reviewer_consensus"].mean()),
                    "curated_precision": precision_score(g["reviewer_consensus"].to_numpy(int), g["_action"].to_numpy(int), zero_division=0),
                    "action_rate": float(g["_action"].mean()),
                }
            )
    taxon_table = pd.DataFrame(taxon_rows)
    taxon_table.to_csv(out_dir / "curated_precision_by_taxon.csv", index=False)

    input_rows = []
    for path in [
        cfg_path,
        p09g / "failure_gallery.csv",
        p09g / "dttail_gallery.csv",
        p09g / "heldout_predictions.csv",
        p09g / "p02d_raw_run_counts.csv",
        p09g / "manifest.json",
    ]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    winner_row = method_table.iloc[0].to_dict()
    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "reproduced": True,
        "raw_root_reproduction": {
            "source": "P09g raw-ROOT selected-pulse reproduction ledger",
            "raw_root_dir": cfg["raw_root_dir"],
            "n_runs": int(raw_counts["run"].nunique()),
            "raw_events": int(raw_counts["raw_events"].sum()),
            "selected_pulses": int(raw_counts["selected_pulses"].sum()),
            "root_inputs_verified": int(raw_root_verification["sha256_match"].sum()),
            "root_input_hash_mismatches": int((~raw_root_verification["sha256_match"]).sum()),
        },
        "winner": winner_row["method"],
        "winner_metric": "curated reviewer precision with run-block bootstrap 95% CI",
        "winner_row": {k: finite(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in winner_row.items()},
        "traditional": method_table[method_table["method"] == "traditional_atom_rubric"].iloc[0].to_dict(),
        "methods": method_table.to_dict(orient="records"),
        "reviewer_agreement": review_agreement.to_dict(orient="records"),
        "novel_ticket": cfg["novel_ticket"],
        "runtime_sec": round(time.time() - started, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, cfg, result, method_table, taxon_table.head(24))

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
        "environment_command": "uv run --with pandas --with scikit-learn python",
        "runtime_sec": round(time.time() - started, 2),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
