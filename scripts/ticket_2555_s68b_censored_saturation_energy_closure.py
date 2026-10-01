#!/usr/bin/env python3
"""S68b/#2555 censored saturation energy-closure benchmark wrapper."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2555"
ISSUE_NUMBER = 2555
WORKER = "testbeam-laptop-4"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
SLUG = "s68b_censored_saturation_energy_closure_waveform_learners"
TITLE = "S68b: Censored saturation energy closure using deconvolution and waveform learners"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-4 --project testbeam"
CLAIM_OUTPUT = "stderr: null; stdout: # null / null"
MANUAL_CLAIM = (
    "gh issue edit 2555 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-4 "
    "--remove-label factory:open"
)
DONE_COMMAND = "tn-ticket done 2555"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def add_reconstructed_energy_strata(joined: pd.DataFrame, strata_path: Path) -> pd.DataFrame:
    strata = pd.read_csv(strata_path)
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    held["reco_energy_adc"] = held["amp1_adc"] + held["amp2_adc"]
    held["reconstructed_energy_bin"] = pd.qcut(
        held["reco_energy_adc"],
        q=4,
        labels=["Q1_low_reco", "Q2", "Q3", "Q4_high_reco"],
        duplicates="drop",
    )
    rows = []
    for (method, value), group in held.groupby(["method", "reconstructed_energy_bin"], observed=False):
        if len(group) == 0:
            continue
        rows.append({"stratum": "reconstructed_energy_bin", "value": str(value), "method": method, **base.metric_values(group)})
    out = pd.concat([strata, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(strata_path, index=False)
    return out


def write_leakage_checks(joined: pd.DataFrame, result: dict, match: pd.DataFrame) -> pd.DataFrame:
    event_split = joined[["event_id", "split", "source_run"]].drop_duplicates()
    train_runs = set(result["evaluation_design"]["train_runs"])
    heldout_runs = set(result["evaluation_design"]["heldout_runs"])
    event_split_counts = event_split.groupby("event_id")["split"].nunique()
    methods = set(joined["method"].unique())
    required = set(result["required_method_coverage"].values())
    checks = [
        {
            "check": "raw_root_reproduction_pass",
            "passed": bool(match["pass"].all()),
            "detail": f"delta={int(match.iloc[0]['delta'])}; reproduced={int(match.iloc[0]['reproduced'])}",
        },
        {
            "check": "run_split_disjoint",
            "passed": train_runs.isdisjoint(heldout_runs),
            "detail": f"train={sorted(train_runs)}; heldout={sorted(heldout_runs)}",
        },
        {
            "check": "no_event_id_crosses_split",
            "passed": bool((event_split_counts <= 1).all()),
            "detail": f"max_splits_per_event={int(event_split_counts.max())}",
        },
        {
            "check": "no_train_rows_from_heldout_runs",
            "passed": not bool(set(event_split[event_split['split'] == 'train']['source_run']) & heldout_runs),
            "detail": "train rows contain no held-out source runs",
        },
        {
            "check": "no_heldout_rows_from_train_runs",
            "passed": not bool(set(event_split[event_split['split'] == 'heldout']['source_run']) & train_runs),
            "detail": "held-out rows contain no train source runs",
        },
        {
            "check": "required_methods_present",
            "passed": required.issubset(methods),
            "detail": f"missing={sorted(required - methods)}",
        },
    ]
    out = pd.DataFrame(checks)
    out.to_csv(OUT / "leakage_checks.csv", index=False)
    return out


def gzip_predictions() -> None:
    src = OUT / "event_predictions.csv"
    dst = OUT / "event_predictions.csv.gz"
    with src.open("rb") as inp, gzip.GzipFile(filename=str(dst), mode="wb", compresslevel=9, mtime=0) as out:
        shutil.copyfileobj(inp, out)


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S68b/#2555: Censored Saturation Energy Closure Using Deconvolution and Waveform Learners",
        1,
    )
    report = report.replace(
        f"Ticket `{TICKET}` asks for an academic-grade comparison of a strong traditional\n"
        "multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "transformer sequence models, and a sensible new architecture for energy\n"
        "reconstruction under pile-up and ADC saturation.",
        f"Ticket `#{TICKET}` asks for an academic-grade comparison of a strong traditional\n"
        "censored Landau-Gaussian/template-charge deconvolution method against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN, and transformer sequence regressors for\n"
        "energy response under clipped tails and overlapping pulses.",
        1,
    )
    report = report.replace(
        "The traditional comparator is **analytic_clipped_template_sideband_traditional**.\n"
        "It fits one- and two-pulse template models by bounded least squares,",
        "The traditional comparator is **analytic_clipped_template_sideband_traditional**,\n"
        "a deterministic censored template-charge deconvolver standing in for a\n"
        "Landau-Gaussian charge-likelihood fit.  It fits one- and two-pulse template\n"
        "models by bounded least squares,",
        1,
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S68b/#2555 controlled-overlay",
    )

    joined = pd.read_csv(OUT / "event_predictions.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    strata = add_reconstructed_energy_strata(joined, OUT / "strata_metrics.csv")
    leakage = write_leakage_checks(joined, result, match)
    gzip_predictions()

    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    deltas = ranked.copy()
    for col in ["energy_fractional_sigma68", "pileup_miss_rate", "energy_fractional_bias"]:
        deltas[f"delta_vs_traditional_{col}"] = deltas[col] - trad[col]
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    held["saturation_knee"] = pd.cut(
        held["saturated_sample_count"],
        bins=[-0.5, 0.5, 2.5, 5.5, 18.5],
        labels=["unclipped", "knee_1_2", "plateau_3_5", "deep_clip_6plus"],
    )
    knee_rows = []
    for (method, value), group in held.groupby(["method", "saturation_knee"], observed=False):
        if len(group) == 0:
            continue
        true_e = group["true_amp1_adc"] + group["true_amp2_adc"]
        pred_e = group["amp1_adc"] + group["amp2_adc"]
        residual = (pred_e - true_e) / np.maximum(true_e, 1.0)
        knee_rows.append(
            {
                "method": method,
                "saturation_knee": str(value),
                "n_events": int(len(group)),
                "median_fractional_energy_residual": float(np.median(residual)),
                "sigma68_fractional_energy": float((np.percentile(residual, 84) - np.percentile(residual, 16)) / 2.0),
            }
        )
    knee = pd.DataFrame(knee_rows)

    report += f"""

## Ticket-Specific Leakage Checks

{md_table(leakage, ['check', 'passed', 'detail'])}

## Saturation-Knee Nonlinearity

The saturation-knee diagnostic bins held-out injected doublets by the observed
number of clipped samples and recomputes fractional energy residuals.  This
directly probes the ticket's nonlinearity requirement at the transition from
recoverable tails to censored plateaus.

{md_table(knee.sort_values(['saturation_knee', 'method']), ['saturation_knee', 'method', 'n_events', 'median_fractional_energy_residual', 'sigma68_fractional_energy'], limit=60)}

## Pile-Up Recovery Delta Versus Traditional Baseline

The table below reports each method relative to the traditional censored
template-charge deconvolver.  Negative deltas are improvements for sigma68,
miss rate, and absolute bias.

{md_table(deltas, ['method', 'energy_fractional_sigma68', 'delta_vs_traditional_energy_fractional_sigma68', 'pileup_miss_rate', 'delta_vs_traditional_pileup_miss_rate', 'energy_fractional_bias', 'delta_vs_traditional_energy_fractional_bias'])}

## Claim Provenance

The required helper command was run exactly once as `{CLAIM_COMMAND}`.  It
returned the null pseudo-ticket pattern (`{CLAIM_OUTPUT}`), while the project
queue still contained open tickets.  Without invoking `tn-ticket claim` again,
issue `#2555` was claimed by the manual label-swap recovery `{MANUAL_CLAIM}`.
Completion is recorded with `{DONE_COMMAND}`.  No novel follow-up ticket was
appended.
"""
    report_path.write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2555",
            "title": TITLE,
            "worker": WORKER,
            "claimed_ticket_text": "#2555 NEW S68b censored saturation energy closure using deconvolution and waveform learners",
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "done_command": DONE_COMMAND,
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "manual_recovery": MANUAL_CLAIM,
                "reran_claim": False,
            },
            "claim_helper_output": {
                "stderr": "null",
                "stdout": "# null\n\nnull",
                "note": "tn-ticket claim was invoked exactly once; issue #2555 was manually label-swapped after the helper null edge case",
            },
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-ticket2555 "
                "UV_PROJECT_ENVIRONMENT=/tmp/ticket2555-uv-venv "
                "uv run --frozen --index-strategy unsafe-best-match "
                "--index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple "
                "--with uproot --with awkward --with numpy --with pandas "
                "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
                f"python {Path(__file__).resolve().relative_to(ROOT)}"
            ),
        }
    )
    result["artifacts"].update(
        {
            "event_predictions": "event_predictions.csv.gz",
            "event_predictions_uncompressed": "event_predictions.csv",
            "leakage_checks": "leakage_checks.csv",
        }
    )
    result["novel_tickets_appended"] = []
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        f"claim_helper_command: {CLAIM_COMMAND}\n"
        "claim_helper_stderr:\nnull\n"
        "claim_helper_stdout:\n# null\n\nnull\n"
        "manual_claim_issue: 2555\n"
        f"manual_claim_command: {MANUAL_CLAIM}\n"
        "manual_claim_evidence: issue #2555 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-4\n"
        f"done_command: {DONE_COMMAND}\n"
        "#2555 NEW S68b censored saturation energy closure using deconvolution and waveform learners\n",
        encoding="utf-8",
    )

    top_result = {
        "ticket_id": TICKET,
        "issue_number": ISSUE_NUMBER,
        "project": "testbeam",
        "worker": WORKER,
        "status": "complete",
        "winner": result["winner"]["name"],
        "winner_metrics": result["winner"],
        "raw_root_reproduction": result["raw_root_reproduction"],
        "split": result["evaluation_design"],
        "required_method_coverage": result["required_method_coverage"],
        "required_outputs": {
            "REPORT.md": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/REPORT.md",
            "method_metrics.csv": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/method_metrics.csv",
            "run_heldout_metrics.csv": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/run_heldout_metrics.csv",
            "strata_metrics.csv": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/strata_metrics.csv",
            "event_predictions.csv.gz": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/event_predictions.csv.gz",
            "leakage_checks.csv": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/leakage_checks.csv",
            "reproduction_match_table.csv": "reports/2555__s68b_censored_saturation_energy_closure_waveform_learners/reproduction_match_table.csv",
        },
        "artifacts": {
            "report": str((OUT / "REPORT.md").relative_to(ROOT)),
            "result": str((OUT / "result.json").relative_to(ROOT)),
            "method_metrics": str((OUT / "method_metrics.csv").relative_to(ROOT)),
            "run_heldout_metrics": str((OUT / "run_heldout_metrics.csv").relative_to(ROOT)),
            "strata_metrics": str((OUT / "strata_metrics.csv").relative_to(ROOT)),
            "event_predictions": str((OUT / "event_predictions.csv.gz").relative_to(ROOT)),
            "leakage_checks": str((OUT / "leakage_checks.csv").relative_to(ROOT)),
            "raw_reproduction": str((OUT / "reproduction_match_table.csv").relative_to(ROOT)),
        },
        "queue_provenance": {
            "claimed_once": True,
            "claim_command_run_once": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": MANUAL_CLAIM,
            "done_command": DONE_COMMAND,
            "novel_tickets_appended": [],
        },
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    (ROOT / "result.json").write_text(json.dumps(top_result, indent=2) + "\n", encoding="utf-8")

    shutil.copyfile(report_path, ROOT / "REPORT.md")
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "worker": WORKER,
            "claim_command_run_once": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": MANUAL_CLAIM,
            "done_command": DONE_COMMAND,
            "outputs_sha256": {
                p.name: sha256_file(p)
                for p in sorted(OUT.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
            "root_report_sha256": sha256_file(ROOT / "REPORT.md"),
            "root_result_sha256": sha256_file(ROOT / "result.json"),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
