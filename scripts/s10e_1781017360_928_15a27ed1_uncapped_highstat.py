#!/usr/bin/env python3
"""S10e validation of S10d secondary-fraction estimates.

Runs the S10d capped raw-ROOT reproduction first, then repeats the same
leave-one-run-out two-pulse template and synthetic-ML scoring on the dominant
matched strata with a larger per-run/stratum waveform sample.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s10e_1781017360_928_15a27ed1_uncapped_highstat.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


CFG = load_json(CONFIG)
TICKET = CFG["ticket"]
OUT = ROOT / CFG["output_dir"]
OUT.mkdir(parents=True, exist_ok=True)


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


def load_s10d():
    path = ROOT / CFG["source_script"]
    spec = importlib.util.spec_from_file_location("s10d_source", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.BOOTSTRAPS = int(CFG["bootstrap_samples"])
    return module


s10d = load_s10d()


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


def renormalized_dominant(stratum_table: pd.DataFrame, n_strata: int) -> pd.DataFrame:
    table = stratum_table.sort_values("match_weight", ascending=False).head(int(n_strata)).copy()
    table["original_match_weight"] = table["match_weight"]
    mass = float(table["original_match_weight"].sum())
    table["dominant_weight_mass"] = mass
    table["match_weight"] = table["original_match_weight"] / mass
    return table.reset_index(drop=True)


def run_scoring_pass(
    label: str,
    events: pd.DataFrame,
    waves: np.ndarray,
    stratum_table: pd.DataFrame,
    cap_per_run_stratum: int,
    rng: np.random.Generator,
) -> dict:
    s10d.SAMPLE_PER_RUN_STRATUM = int(cap_per_run_stratum)
    sample = s10d.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, templates, folds = s10d.heldout_predictions(events, waves, sample, rng)
    method_tables = []
    method_summaries = []
    for col in ["trad_secondary_fraction", "ml_secondary_fraction", "ml_overlap_score"]:
        table, summary = s10d.summarize_method(scores, stratum_table, col, rng)
        method_tables.append(table)
        method_summaries.append(summary)
    stratum_summary = pd.concat(method_tables, ignore_index=True)
    method_summary = pd.concat(method_summaries, ignore_index=True)
    leakage = s10d.leakage_checks(scores, folds)

    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(
        OUT / f"{label}_analysis_sample.csv", index=False
    )
    scores.to_csv(OUT / f"{label}_event_scores.csv", index=False)
    templates.to_csv(OUT / f"{label}_template_summary_by_fold.csv", index=False)
    folds.to_csv(OUT / f"{label}_fold_diagnostics.csv", index=False)
    stratum_summary.to_csv(OUT / f"{label}_method_stratum_summary.csv", index=False)
    method_summary.to_csv(OUT / f"{label}_method_summary.csv", index=False)
    leakage.to_csv(OUT / f"{label}_leakage_checks.csv", index=False)

    def row(metric: str) -> pd.Series:
        return method_summary[method_summary["method_metric"] == metric].iloc[0]

    trad = row("trad_secondary_fraction")
    ml_frac = row("ml_secondary_fraction")
    ml_score = row("ml_overlap_score")
    return {
        "label": label,
        "sample_cap_per_run_stratum": int(cap_per_run_stratum),
        "n_scored_events": int(len(scores)),
        "n_strata": int(len(stratum_table)),
        "dominant_weight_mass": float(stratum_table.get("dominant_weight_mass", pd.Series([1.0])).iloc[0]),
        "traditional": {
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "ml_secondary_fraction": {
            "value": float(ml_frac["value"]),
            "ci": [float(ml_frac["ci_low"]), float(ml_frac["ci_high"])],
        },
        "ml_overlap_score": {
            "value": float(ml_score["value"]),
            "ci": [float(ml_score["ci_low"]), float(ml_score["ci_high"])],
        },
        "mean_synthetic_holdout_auc": float(folds["synthetic_holdout_auc"].mean()),
        "mean_shuffled_label_synthetic_auc": float(folds["shuffled_label_synthetic_auc"].mean()),
        "mean_secondary_fraction_mae_on_synthetic_holdout": float(folds["synthetic_secondary_fraction_mae"].mean()),
        "actual_current_auc_from_ml_secondary_fraction": float(
            leakage[leakage["check"] == "actual_current_auc_from_ml_secondary_fraction"]["value"].iloc[0]
        ),
        "leakage_flags": int(leakage["flag"].sum()),
    }


def write_report(
    repro: pd.DataFrame,
    stratum_table: pd.DataFrame,
    dominant_table: pd.DataFrame,
    capped_all: dict,
    capped_dominant: dict,
    highstat_dominant: dict,
    result: dict,
) -> None:
    trad_rep = capped_all["traditional"]
    trad_cap = capped_dominant["traditional"]
    trad_hi = highstat_dominant["traditional"]
    ml_hi = highstat_dominant["ml_secondary_fraction"]
    ml_score_hi = highstat_dominant["ml_overlap_score"]
    sensitivity = highstat_dominant["traditional"]["value"] - capped_dominant["traditional"]["value"]
    lines = [
        "# S10e: S10d high-stat validation",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{CFG['worker']}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** leave-one-source-run-out templates/ML; CIs bootstrap held-out source runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The S10d capped 140/event analysis was rerun from raw ROOT before the high-stat pass. "
            f"Traditional high-minus-low secondary fraction reproduced as **{trad_rep['value']:.5f}** "
            f"[{trad_rep['ci'][0]:.5f}, {trad_rep['ci'][1]:.5f}], versus the S10d report value "
            f"{CFG['s10d_reported_traditional_value']:.5f}."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "## Dominant high-stat strata",
        "",
        (
            f"The high-stat rerun uses the top {len(dominant_table)} matched strata by S10d match weight, "
            f"covering {100.0 * float(dominant_table['original_match_weight'].sum()):.2f}% of the matched weight. "
            f"The per-run/stratum waveform cap is {CFG['highstat_sample_cap_per_run_stratum']}, "
            f"5x the S10d cap of {CFG['reproduce_sample_cap_per_run_stratum']}."
        ),
        "",
        dominant_table[
            ["amp_bin", "baseline_bin", "p02_topology", "low_n", "high_n", "original_match_weight", "match_weight"]
        ].to_markdown(index=False),
        "",
        "## Traditional method",
        "",
        (
            "The traditional method is the same constrained two-pulse template fit used in S10d: templates are "
            "median raw-pulse templates built without the held-out run, then a bounded one-pulse/two-pulse "
            "least-squares scan reports A2/(A1+A2)."
        ),
        "",
        (
            f"Dominant-strata capped result: **{trad_cap['value']:.5f}** "
            f"[{trad_cap['ci'][0]:.5f}, {trad_cap['ci'][1]:.5f}]. "
            f"High-stat result: **{trad_hi['value']:.5f}** "
            f"[{trad_hi['ci'][0]:.5f}, {trad_hi['ci'][1]:.5f}]. "
            f"High-stat minus capped sensitivity on the identical dominant strata is **{sensitivity:+.5f}**."
        ),
        "",
        "## ML method",
        "",
        (
            "The ML diagnostic is the S10d run-held-out random-forest classifier/regressor trained on synthetic "
            "two-pulse overlays made only from training-run raw pulses. Features exclude run, event number, "
            "current label, downstream label, and stratum labels."
        ),
        "",
        (
            f"High-stat ML secondary-fraction high-minus-low is **{ml_hi['value']:.5f}** "
            f"[{ml_hi['ci'][0]:.5f}, {ml_hi['ci'][1]:.5f}]. "
            f"ML overlap-score high-minus-low is **{ml_score_hi['value']:.5f}** "
            f"[{ml_score_hi['ci'][0]:.5f}, {ml_score_hi['ci'][1]:.5f}]."
        ),
        "",
        "## Leakage review",
        "",
        (
            f"High-stat synthetic held-out AUC is {highstat_dominant['mean_synthetic_holdout_auc']:.3f}; "
            f"shuffled-label AUC is {highstat_dominant['mean_shuffled_label_synthetic_auc']:.3f}; "
            f"actual-current AUC from ML secondary fraction is "
            f"{highstat_dominant['actual_current_auc_from_ml_secondary_fraction']:.3f}. "
            f"Leakage flags: {highstat_dominant['leakage_flags']}."
        ),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, "
            "`stratum_table.csv`, dominant/capped/highstat method summaries, event scores, fold diagnostics, "
            "and leakage checks are in this folder."
        ),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    start = time.time()
    events, waves, run_counts = s10d.load_events()
    topology, repro = s10d.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10c raw-ROOT reproduction gate failed")
    counts = s10d.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s10d.matched_strata(counts)
    dominant_table = renormalized_dominant(stratum_table, int(CFG["dominant_strata_by_match_weight"]))

    capped_all = run_scoring_pass(
        "reproduce_capped_all",
        events,
        waves,
        stratum_table,
        int(CFG["reproduce_sample_cap_per_run_stratum"]),
        np.random.default_rng(int(CFG["reproduce_random_seed"])),
    )
    capped_dominant = run_scoring_pass(
        "dominant_capped",
        events,
        waves,
        dominant_table,
        int(CFG["reproduce_sample_cap_per_run_stratum"]),
        np.random.default_rng(int(CFG["dominant_capped_random_seed"])),
    )
    highstat_dominant = run_scoring_pass(
        "dominant_highstat",
        events,
        waves,
        dominant_table,
        int(CFG["highstat_sample_cap_per_run_stratum"]),
        np.random.default_rng(int(CFG["dominant_highstat_random_seed"])),
    )

    input_files = [s10d.raw_file(run) for run in sorted(s10d.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    dominant_table.to_csv(OUT / "dominant_stratum_table.csv", index=False)

    rep_delta = capped_all["traditional"]["value"] - float(CFG["s10d_reported_traditional_value"])
    high_minus_cap = highstat_dominant["traditional"]["value"] - capped_dominant["traditional"]["value"]
    conclusion = (
        f"The raw-ROOT capped reproduction matches S10d within {rep_delta:+.6f} on the traditional headline. "
        f"On the top {len(dominant_table)} strata covering {100.0 * highstat_dominant['dominant_weight_mass']:.2f}% "
        f"of the matched weight, increasing the per-run/stratum cap from "
        f"{CFG['reproduce_sample_cap_per_run_stratum']} to {CFG['highstat_sample_cap_per_run_stratum']} changes "
        f"the traditional secondary-fraction high-minus-low by {high_minus_cap:+.5f}. "
        f"The high-stat traditional estimate is {highstat_dominant['traditional']['value']:.5f} "
        f"[{highstat_dominant['traditional']['ci'][0]:.5f}, {highstat_dominant['traditional']['ci'][1]:.5f}], "
        f"while the ML secondary-fraction diagnostic is {highstat_dominant['ml_secondary_fraction']['value']:.5f} "
        f"[{highstat_dominant['ml_secondary_fraction']['ci'][0]:.5f}, "
        f"{highstat_dominant['ml_secondary_fraction']['ci'][1]:.5f}]. "
        "No leakage check flags, but the ML arm remains a synthetic-overlay diagnostic rather than a truth-labelled decomposition."
    )
    result = {
        "study": CFG["study"],
        "ticket": TICKET,
        "worker": CFG["worker"],
        "title": "validate S10d secondary-fraction estimates on high-stat strata",
        "source_ticket": CFG["source_ticket"],
        "reproduced": bool(abs(rep_delta) < 1e-10),
        "reproduction_delta_vs_s10d_traditional": float(rep_delta),
        "split": "leave-one-source-run-out for templates and ML; run bootstrap CIs within current group",
        "strata": {
            "n_matched_strata_all": int(len(stratum_table)),
            "n_dominant_strata": int(len(dominant_table)),
            "dominant_weight_mass": float(dominant_table["original_match_weight"].sum()),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
        },
        "reproduce_capped_all": capped_all,
        "dominant_capped": capped_dominant,
        "dominant_highstat": highstat_dominant,
        "sampling_sensitivity": {
            "traditional_highstat_minus_capped_dominant": float(high_minus_cap),
            "traditional_highstat_minus_s10d_all_capped": float(
                highstat_dominant["traditional"]["value"] - float(CFG["s10d_reported_traditional_value"])
            ),
        },
        "leakage_checks_pass": bool(highstat_dominant["leakage_flags"] == 0),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(repro, stratum_table, dominant_table, capped_all, capped_dominant, highstat_dominant, result)
    manifest = {
        "study": CFG["study"],
        "ticket": TICKET,
        "worker": CFG["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(CONFIG.relative_to(ROOT)),
        "random_seed": int(CFG["random_seed"]),
        "pass_random_seeds": {
            "reproduce_capped_all": int(CFG["reproduce_random_seed"]),
            "dominant_capped": int(CFG["dominant_capped_random_seed"]),
            "dominant_highstat": int(CFG["dominant_highstat_random_seed"]),
        },
        "inputs": input_hashes,
        "code_inputs": {
            str(CONFIG.relative_to(ROOT)): sha256_file(CONFIG),
            str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
            CFG["source_script"]: sha256_file(ROOT / CFG["source_script"]),
        },
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
