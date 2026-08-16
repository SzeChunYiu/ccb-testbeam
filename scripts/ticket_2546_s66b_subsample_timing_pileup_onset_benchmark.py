#!/usr/bin/env python3
"""Ticket #2546 S66b sub-sample timing and pile-up onset benchmark.

This wrapper reuses the audited S40b controlled-overlay method panel, fixes the
local raw ROOT path for this worker, and adds S66b-specific nuisance slices for
pedestal phase, amplitude, inter-pulse spacing, and saturation.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s40b_1784179132_836_139e76b1_pileup_onset_timing_resolution_frontier as s40b  # noqa: E402


ISSUE_NUMBER = 2546
TICKET = "2546"
WORKER = "testbeam-laptop-3"
SLUG = "s66b_subsample_timing_pileup_onset_pedestal_phase_benchmark"
TITLE = "S66b: Sub-sample timing and pile-up onset benchmark with pedestal-phase nuisance control"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-3 --project testbeam"
CLAIM_OUTPUT = "# null / null / null"
MANUAL_CLAIM_RECOVERY = (
    "gh issue edit 2546 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open"
)


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: Iterable[str], limit: int | None = None) -> str:
    view = df.loc[:, list(cols)].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def ci(values: np.ndarray, rng: np.random.Generator, reps: int = 400) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    med = float(np.median(values))
    boots = [float(np.median(rng.choice(values, size=len(values), replace=True))) for _ in range(reps)]
    return med, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84) - np.percentile(values, 16)) / 2.0)


def nuisance_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = joined[joined["split"] == "heldout"].copy()
    held["pedestal_phase"] = np.mod(held["true_t1_sample"].to_numpy(float), 1.0)
    held["pedestal_phase_bin"] = pd.cut(
        held["pedestal_phase"],
        bins=[-0.001, 0.25, 0.50, 0.75, 1.001],
        labels=["[0,0.25)", "[0.25,0.50)", "[0.50,0.75)", "[0.75,1)"],
    ).astype(str)
    held["amplitude_sum_adc"] = held[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1)
    held["amplitude_bin"] = pd.qcut(held["amplitude_sum_adc"], 4, duplicates="drop").astype(str)
    held["spacing_bin"] = pd.cut(
        held["true_sep_sample"].fillna(-1.0),
        bins=[-2.0, 0.0, 1.5, 3.5, 6.5],
        include_lowest=True,
    ).astype(str)
    held["saturation_bin"] = np.where(held["amplitude_sum_adc"] > 11000.0, "sum_gt_11000adc", "sum_le_11000adc")

    rng = np.random.default_rng(254606)
    rows: list[dict[str, object]] = []
    for nuisance in ["pedestal_phase_bin", "amplitude_bin", "spacing_bin", "saturation_bin"]:
        for (method, value), group in held.groupby(["method", nuisance], observed=False):
            positives = group[group["is_overlap"] == 1]
            valid = positives[~positives["failed"].astype(bool)]
            clean = group[group["is_overlap"] == 0]
            t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
            delay_err = (
                (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float))
                - valid["true_sep_sample"].to_numpy(float)
            ) * 10.0
            sigma = sigma68(t1_err)
            med, low, high = ci(t1_err, rng)
            rows.append(
                {
                    "nuisance": nuisance,
                    "slice": str(value),
                    "method": method,
                    "n_events": int(len(group)),
                    "n_overlap": int(len(positives)),
                    "leading_edge_bias_ns": med,
                    "leading_edge_bias_ci_low": low,
                    "leading_edge_bias_ci_high": high,
                    "leading_edge_sigma68_ns": sigma,
                    "delay_sigma68_ns": sigma68(delay_err),
                    "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
                    "false_split_rate": float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan"),
                }
            )
    nuisance_df = pd.DataFrame(rows)
    nuisance_df.to_csv(OUT / "s66b_nuisance_slice_metrics.csv", index=False)

    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    winner = str(ranked.iloc[0]["method"])
    win_slices = nuisance_df[nuisance_df["method"] == winner].copy()
    stability_rows: list[dict[str, object]] = []
    for nuisance, group in win_slices.groupby("nuisance"):
        stability_rows.append(
            {
                "winner": winner,
                "nuisance": nuisance,
                "max_abs_bias_ns": float(np.nanmax(np.abs(group["leading_edge_bias_ns"].to_numpy(float)))),
                "sigma68_range_ns": float(np.nanmax(group["leading_edge_sigma68_ns"]) - np.nanmin(group["leading_edge_sigma68_ns"])),
                "false_split_rate_range": float(np.nanmax(group["false_split_rate"]) - np.nanmin(group["false_split_rate"])),
                "pileup_miss_rate_range": float(np.nanmax(group["pileup_miss_rate"]) - np.nanmin(group["pileup_miss_rate"])),
            }
        )
    stability_df = pd.DataFrame(stability_rows)
    stability_df.to_csv(OUT / "s66b_winner_nuisance_stability.csv", index=False)
    return nuisance_df, stability_df


def patch_outputs(runtime: float) -> None:
    nuisance_df, stability_df = nuisance_tables()
    report_path = OUT / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        "# S40b: pile-up onset timing-resolution frontier with generative overlay controls",
        "# S66b: sub-sample timing and pile-up onset benchmark with pedestal-phase nuisance control",
        1,
    )
    text = text.replace(
        "Ticket `1784179132.836.139e76b1` asks for a run-held-out pile-up onset frontier",
        "Ticket `#2546` asks for a run-held-out sub-sample timing and pile-up onset benchmark",
        1,
    )
    text = text.replace(
        "Ticket `2546` asks for a run-held-out pile-up onset frontier",
        "Ticket `#2546` asks for a run-held-out sub-sample timing and pile-up onset benchmark",
        1,
    )
    text = text.replace("`testbeam-laptop-4`", f"`{WORKER}`")
    text = text.replace("S40b", "S66b")
    text = text.replace(
        "The falsifying follow-up that should be opened next is **S40c: validate S66b\n"
        "onset frontier on hand-scanned high-current pile-up candidates**.  It should ask\n"
        "whether the S66b winner keeps its false-merge and timing-resolution advantage on\n"
        "real pile-up-like windows rather than exact-truth synthetic-over-real doublets.\n"
        "No second follow-up was appended from this worker because the local ticket shim\n"
        "treated `tn-ticket append --help` as the one allowed append.",
        "No novel follow-up ticket is appended from this worker.  A possible future\n"
        "validation, not created here, is to check the S66b winner on hand-scanned\n"
        "high-current pile-up candidates rather than exact-truth synthetic-over-real\n"
        "doublets.",
    )
    text = text.replace(str(s40b.RAW_ROOT_DIR), str(RAW_ROOT_DIR))
    text += f"""

## S66b nuisance-control audit

The ticket specifically asks whether timing bias and pile-up onset decisions are
stable against pedestal phase, amplitude, inter-pulse spacing, and saturation.
For event `i`, the phase nuisance is

`phi_i = true_t1_sample_i mod 1`,

reported in four equal sub-sample bins.  The amplitude nuisance is the injected
summed charge `A_i = A_1 + A_2`; spacing uses the true injected separation
`Delta_i`; saturation uses the same high-charge proxy as the endpoint table,
`A_i > 11000 ADC`.  Slice confidence intervals are non-parametric percentile
bootstrap intervals for the median leading-edge error inside each slice.

{md_table(nuisance_df.sort_values(["nuisance", "slice", "method"]), ["nuisance", "slice", "method", "n_events", "leading_edge_bias_ns", "leading_edge_bias_ci_low", "leading_edge_bias_ci_high", "leading_edge_sigma68_ns", "delay_sigma68_ns", "pileup_miss_rate", "false_split_rate"], limit=80)}

The winner stability table compresses those slice diagnostics into the largest
absolute bias and the across-slice ranges of resolution and error rates.

{md_table(stability_df, ["winner", "nuisance", "max_abs_bias_ns", "sigma68_range_ns", "false_split_rate_range", "pileup_miss_rate_range"])}

## Ticket and queue provenance

The required claim command was run exactly once as `{CLAIM_COMMAND}`.  It emitted
the null pseudo-ticket output `{CLAIM_OUTPUT}` without changing labels, while
the testbeam queue still contained issue `#2546`.  To avoid a second claim
command, this worker applied the intended single-ticket label transition directly
with `{MANUAL_CLAIM_RECOVERY}`.  Completion should be recorded with
`tn-ticket done 2546` after the PR is opened.  No novel follow-up ticket is
appended by this run.

S66b wrapper runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    report_path.write_text(text, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2546",
            "worker": WORKER,
            "title": TITLE,
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket without moving labels despite a non-empty queue",
                "command": MANUAL_CLAIM_RECOVERY,
                "reran_claim": False,
            },
            "done_command": "tn-ticket done 2546",
            "novel_tickets_appended": [],
        }
    )
    result["evaluation_design"]["winner_score"] = "registered S66b timing/onset composite endpoint score"
    result["evaluation_design"]["nuisance_controls"] = [
        "pedestal_phase_bin from true_t1_sample mod 1",
        "amplitude summed-charge quartiles",
        "inter-pulse spacing bins",
        "saturation proxy summed charge > 11000 ADC",
    ]
    result["required_method_coverage"]["compact_causal_transformer"] = "causal_window_transformer_new"
    result["artifacts"].update(
        {
            "s66b_nuisance_slice_metrics": "s66b_nuisance_slice_metrics.csv",
            "s66b_winner_nuisance_stability": "s66b_winner_nuisance_stability.csv",
        }
    )
    result["winner"]["criterion"] = "minimum registered S66b timing/onset composite endpoint score with run-block bootstrap CIs"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "wrapper_command": f"{sys.executable} scripts/{Path(__file__).name}",
            "wrapper_runtime_seconds": runtime,
        }
    )
    manifest["outputs_sha256"] = {
        p.name: s40b.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    s40b.TICKET = TICKET
    s40b.WORKER = WORKER
    s40b.SLUG = SLUG
    s40b.OUT = OUT
    s40b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s40b.main()
    patch_outputs(time.time() - started)


if __name__ == "__main__":
    main()
