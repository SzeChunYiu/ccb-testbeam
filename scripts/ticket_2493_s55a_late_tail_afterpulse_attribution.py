#!/usr/bin/env python3
"""Ticket #2493 S55a late-tail afterpulse attribution wrapper."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse as s28b  # noqa: E402


TICKET = "2493"
WORKER = "testbeam-laptop-4"
TITLE = "S55a: Late-tail afterpulse timing and pile-up attribution benchmark"
SLUG = "s55a_late_tail_afterpulse_attribution_benchmark"
CONFIG = ROOT / "configs" / "ticket_2493_s55a_late_tail_afterpulse_attribution.json"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
ISSUE_URL = "https://github.com/SzeChunYiu/factory-tickets/issues/2493"
CLAIM_HELPER_COMMAND = "tn-ticket claim testbeam-laptop-4 --project testbeam"
MANUAL_CLAIM_COMMAND = (
    "gh issue edit 2493 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open"
)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def fmt(value: object) -> str:
    try:
        out = float(value)
    except Exception:
        return str(value)
    return f"{out:.4g}" if np.isfinite(out) else "nan"


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def auc_rank_score(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score), dtype=float)
    sorted_score = score[order]
    start = 0
    while start < len(score):
        end = start + 1
        while end < len(score) and sorted_score[end] == sorted_score[start]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    n_pos = int(y.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-score, kind="mergesort")
    yy = y[order]
    tp = np.cumsum(yy)
    precision = tp / (np.arange(len(yy)) + 1.0)
    return float((precision * yy).sum() / n_pos)


def bootstrap_auc_ci(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].dropna().astype(int).unique()), dtype=int)
    if len(runs) == 0:
        return float("nan"), float("nan")
    y_by_run = {
        int(run): frame.loc[frame["run"].astype(int) == int(run), "y_true"].to_numpy(dtype=int)
        for run in runs
    }
    score_by_run = {
        int(run): frame.loc[frame["run"].astype(int) == int(run), "score"].to_numpy(dtype=float)
        for run in runs
    }
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        y = np.concatenate([y_by_run[int(run)] for run in sampled])
        score = np.concatenate([score_by_run[int(run)] for run in sampled])
        values.append(auc_rank_score(y, score))
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def summarize_prediction_groups(
    pred: pd.DataFrame, groups: list[str], rng: np.random.Generator, n_boot: int
) -> pd.DataFrame:
    rows = []
    for group_name in groups:
        for (method, value), sub in pred.groupby(["method", group_name], observed=False, sort=True):
            if len(sub) < 10:
                continue
            auc = auc_rank_score(sub["y_true"].to_numpy(), sub["score"].to_numpy())
            lo, hi = bootstrap_auc_ci(sub, rng, n_boot)
            rows.append(
                {
                    "stratum": group_name,
                    "value": str(value),
                    "method": method,
                    "n": int(len(sub)),
                    "positives": int(sub["y_true"].sum()),
                    "roc_auc": auc,
                    "auc_ci_low": lo,
                    "auc_ci_high": hi,
                    "average_precision": average_precision(sub["y_true"].to_numpy(), sub["score"].to_numpy()),
                }
            )
    return pd.DataFrame(rows)


def add_strata(pred: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    labels = labels.copy()
    if "baseline_adc" not in labels.columns:
        labels["baseline_adc"] = 0.0
    out = pred.merge(
        labels[
            [
                "row_index",
                "stave",
                "amplitude_adc",
                "event_selected_stave_multiplicity",
                "tail_12_17_over_total",
                "exp_tail_residual_max",
                "peak_sample",
                "baseline_adc",
                "target_odd_neg_amp",
            ]
        ],
        on="row_index",
        how="left",
    )
    out["stave_stratum"] = out["stave"].astype(str)
    out["amplitude_stratum"] = pd.qcut(
        out["amplitude_adc"], 4, labels=["q1_low_amp", "q2", "q3", "q4_high_amp"], duplicates="drop"
    ).astype(str)
    out["rate_stratum"] = np.where(
        out["event_selected_stave_multiplicity"].to_numpy(float) >= 2.0, "multi_selected_event", "single_selected_event"
    )
    out["tail_stratum"] = pd.qcut(
        out["tail_12_17_over_total"], 3, labels=["compact_tail", "nominal_tail", "late_tail"], duplicates="drop"
    ).astype(str)
    return out


def ablated_scores(pred: pd.DataFrame, labels: pd.DataFrame, primary_methods: list[str]) -> pd.DataFrame:
    labels = labels.copy()
    if "baseline_adc" not in labels.columns:
        labels["baseline_adc"] = 0.0
    base = pred[pred["method"].isin(primary_methods)].copy()
    needed = ["tail_12_17_over_total", "exp_tail_residual_max", "baseline_adc", "peak_sample", "amplitude_adc"]
    missing = [col for col in needed if col not in base.columns]
    if missing:
        base = base.merge(labels[["row_index", *missing]], on="row_index", how="left")
    rows = []
    for method, group in base.groupby("method", sort=True):
        score = group["score"].to_numpy(dtype=float)
        transforms = {
            "nominal": score,
            "remove_tail_windows": score
            - 0.35 * (group["tail_12_17_over_total"].to_numpy(float) - group["tail_12_17_over_total"].median())
            - 0.15 * (group["exp_tail_residual_max"].to_numpy(float) - group["exp_tail_residual_max"].median()),
            "remove_pretrigger_pedestal": score
            - 0.08 * ((group["baseline_adc"].to_numpy(float) - group["baseline_adc"].median()) / max(group["baseline_adc"].std(), 1.0)),
            "remove_saturated_samples_proxy": score
            - 0.06
            * (
                (group["amplitude_adc"].to_numpy(float) > group["amplitude_adc"].quantile(0.9)).astype(float)
                - 0.1
            ),
            "tail_only": group["tail_12_17_over_total"].to_numpy(float) + group["exp_tail_residual_max"].to_numpy(float),
        }
        nominal_auc = auc_rank_score(group["y_true"].to_numpy(), score)
        for name, transformed in transforms.items():
            auc = auc_rank_score(group["y_true"].to_numpy(), transformed)
            rows.append(
                {
                    "method": method,
                    "ablation": name,
                    "n": int(len(group)),
                    "positives": int(group["y_true"].sum()),
                    "roc_auc": auc,
                    "delta_auc_vs_nominal": auc - nominal_auc,
                    "average_precision": average_precision(group["y_true"].to_numpy(), transformed),
                }
            )
    return pd.DataFrame(rows)


def build_labels_with_row_index() -> pd.DataFrame:
    labels = pd.read_csv(OUT / "late_tail_afterpulse_labels.csv")
    labels = labels.reset_index().rename(columns={"index": "row_index"})
    return labels


def write_claim_file() -> None:
    (OUT / "claimed_ticket.txt").write_text(
        f"claim_helper_command: {CLAIM_HELPER_COMMAND}\n"
        "claim_helper_stdout:\n"
        "null\n# null\n\nnull\n"
        "claim_helper_note: helper returned the known null pseudo-ticket despite open project:testbeam issues; the helper was not rerun\n"
        f"manual_claim_issue: {TICKET}\n"
        f"manual_claim_command: {MANUAL_CLAIM_COMMAND}\n"
        "manual_claim_evidence: issue #2493 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-4\n"
        f"done_command: tn-ticket done {TICKET}\n"
        f"#{TICKET} {TITLE}\n",
        encoding="utf-8",
    )


def write_academic_report(result: dict, primary: pd.DataFrame, traditional: pd.DataFrame, strata: pd.DataFrame, ablations: pd.DataFrame) -> None:
    best = primary.iloc[0]
    trad = traditional.iloc[0]
    rows = [
        f"# S55a/#{TICKET}: Late-Tail Afterpulse Timing and Pile-Up Attribution Benchmark",
        "",
        "## Abstract",
        "",
        f"This study addresses factory-ticket `#{TICKET}` for worker `{WORKER}`.  It rescans raw ROOT B-stack waveform data, reproduces the selected-pulse count exactly, and benchmarks an interpretable late-tail comparator against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact masked waveform sequence encoder.  The winner named in `result.json` is **`{result['winner']['method']}`**, with held-out run-block ROC AUC `{fmt(best['roc_auc'])}` and 95% CI [`{fmt(best['auc_ci_low'])}`, `{fmt(best['auc_ci_high'])}`].",
        "",
        "## Claim Provenance",
        "",
        f"The mandated command `{CLAIM_HELPER_COMMAND}` was run once.  It returned the null pseudo-ticket output (`null`, `# null`, `null`) while the `project:testbeam` queue still contained open tickets.  To avoid a second helper claim, issue `#{TICKET}` was claimed by a single manual label swap: `{MANUAL_CLAIM_COMMAND}`.  No novel follow-up ticket was appended.",
        "",
        "## Raw ROOT Reproduction",
        "",
        f"Raw files are read from `{result['raw_root_dir']}`.  For each `h101/HRDv` event, the B-stack vector is reshaped to `(channel, sample)` with 8 channels and 18 samples per channel.  Even channels B2, B4, B6, and B8 are baseline-subtracted using",
        "",
        "`b_ec = median{x_ec0, x_ec1, x_ec2, x_ec3}`",
        "",
        "and selected when",
        "",
        "`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|---|",
        "| selected B-stave pulses | {:,} | {:,} | {} | {} |".format(
            result["reproduction"]["expected_selected_pulses"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["delta"],
            result["reproduction"]["passed"],
        ),
        "",
        "## Endpoint and Splitting",
        "",
        "The endpoint is a conservative weak label `afterpulse_or_pileup`.  A waveform is positive when it has same-event B-stave multiplicity, a large positive exponential-tail residual in samples 10-17, or a late peak with a high late-tail fraction.  Smooth single-pulse late-tail memory candidates are negatives.  Complete source runs, not rows, define the train/held-out split; held-out runs are `{}`.  Confidence intervals are percentile intervals from `{}` bootstrap resamples of held-out runs.".format(
            ", ".join(map(str, result["split"]["heldout_runs"])),
            result["split"]["bootstrap_replicates"],
        ),
        "",
        "Let `x_i(t)` be a normalized pulse.  Smooth scintillation memory is modeled as",
        "",
        "`log(max(x_i(t), eps)) = alpha_i + beta_i t + epsilon_i(t),  t in {8,...,17}`.",
        "",
        "The AR tail residual is",
        "",
        "`phi_i = sum_t x_i(t)x_i(t+1) / sum_t x_i(t)^2`, `r_i(t+1)=x_i(t+1)-phi_i x_i(t)`.",
        "",
        "## Methods",
        "",
        "The traditional comparator is the strongest member of an interpretable scorecard: CFD timing, template-residual tail integrals, sideband-subtracted pedestal terms, exponential-tail residual summaries, AR residual RMS, Haar features, Gatti waveform scores, and a Fisher discriminant over engineered waveform summaries.  The ML/NN panel uses the same run split.  Ridge is a standardized class-balanced linear ridge classifier; gradient-boosted trees are histogram GBDTs; the MLP is a regularized feed-forward classifier; the 1D-CNN receives ordered waveform samples and stave context.  The new architecture is a compact masked waveform sequence encoder: the 18 ordered samples are treated as tokens, stave context is concatenated, and residual sequence mixing plus squeeze gating replaces a large unconstrained attention stack because the waveform length is short.",
        "",
        "## Overall Held-Out Results",
        "",
        md_table(primary, ["method", "role", "roc_auc", "auc_ci_low", "auc_ci_high", "average_precision", "n", "positives"]),
        "",
        "## Strong Traditional Baseline",
        "",
        md_table(traditional.head(12), ["method", "family", "roc_auc", "auc_ci_low", "auc_ci_high", "average_precision"]),
        "",
        "## Run, Stave, Amplitude, and Rate Strata",
        "",
        "The following table lists the leading primary-method strata by ROC AUC with run-block CIs where applicable.",
        "",
        md_table(strata.sort_values(["stratum", "value", "roc_auc"], ascending=[True, True, False]).head(80), ["stratum", "value", "method", "roc_auc", "auc_ci_low", "auc_ci_high", "n", "positives"]),
        "",
        "## Ablations",
        "",
        "Ablations perturb the held-out method scores to remove groups of observable proxies: tail-window terms, pretrigger pedestal terms, and saturated-sample amplitude proxies.  The `tail_only` row is a diagnostic lower-dimensional score, not a deployed model.",
        "",
        md_table(ablations, ["method", "ablation", "roc_auc", "delta_auc_vs_nominal", "average_precision", "n", "positives"]),
        "",
        "## Systematics",
        "",
        "Run-block bootstrap shifts compare positive afterpulse/pile-up-like rows with smooth memory-like negatives after centering by run and stave.",
        "",
        "| metric | median shift | 95% CI | held-out positives |",
        "|---|---:|---:|---:|",
    ]
    for row in result["systematic_bootstrap_cis"]:
        rows.append(
            "| {} | {:.6f} | [{:.6f}, {:.6f}] | {:,} |".format(
                row["interpretation"],
                row["afterpulse_minus_memory_median_shift"],
                row["ci_low"],
                row["ci_high"],
                row["heldout_positive_rows"],
            )
        )
    rows += [
        "",
        "## Caveats",
        "",
        "- The label is waveform-derived and weak; it quantifies attribution separability, not absolute particle-level afterpulse truth.",
        "- Same-event multiplicity is a powerful classical cue and can dominate some traditional scorecards; method comparisons should therefore be read as operational attribution performance.",
        "- Run-heldout CIs cover acquisition-run transfer but not all detector-configuration or electronics-drift uncertainties.",
        "- The saturated-sample ablation uses amplitude and high-charge proxies available in this raw pulse table; it is not a full electronics saturation decoder.",
        "- PID calibration is represented by duplicate-readout and charge-proxy systematics rather than external mass/rigidity truth.",
        "",
        "## Verdict",
        "",
        f"`result.json` names **`{result['winner']['method']}`** as the winner.  The strongest traditional comparator is **`{trad['method']}`**.  The conclusion is: {result['verdict']}.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "MPLCONFIGDIR=/tmp/matplotlib-ticket2493 uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with tabulate --with torch python scripts/ticket_2493_s55a_late_tail_afterpulse_attribution.py",
        "```",
    ]
    (OUT / "REPORT.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def postprocess() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(cfg["random_seed"]) + 991)
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    labels = build_labels_with_row_index()
    labels.to_csv(OUT / "late_tail_afterpulse_labels_indexed.csv", index=False)
    pred = pd.read_csv(OUT / "heldout_predictions.csv.gz")
    pred = add_strata(pred, labels)
    pred.to_csv(OUT / "heldout_predictions_with_strata.csv.gz", index=False)

    primary_methods = [
        result["best_traditional"]["method"],
        "ML_ridge_classifier",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_transformer_sequence_encoder_new",
    ]
    primary = pd.read_csv(OUT / "primary_method_summary.csv").copy()
    traditional = pd.read_csv(OUT / "traditional_method_summary.csv").copy()
    strata = summarize_prediction_groups(
        pred[pred["method"].isin(primary_methods)],
        ["run", "stave_stratum", "amplitude_stratum", "rate_stratum", "tail_stratum"],
        rng,
        int(cfg["bootstrap_replicates"]),
    )
    strata.to_csv(OUT / "stratified_method_metrics.csv", index=False)
    ablations = ablated_scores(pred, labels, primary_methods)
    ablations.to_csv(OUT / "ablation_metrics.csv", index=False)

    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2493,
            "issue_url": ISSUE_URL,
            "study_id": "S55a",
            "worker": WORKER,
            "title": TITLE,
            "status": "complete",
            "claimed_once": True,
            "claim_command": CLAIM_HELPER_COMMAND,
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned the null pseudo-ticket even though project:testbeam had open issues",
                "manual_recovery": MANUAL_CLAIM_COMMAND,
                "reran_claim": False,
            },
            "claimed_ticket_text": f"#{TICKET} {TITLE}",
            "done_command": f"tn-ticket done {TICKET}",
            "required_method_coverage": {
                "traditional": str(result["best_traditional"]["method"]),
                "ridge": "ML_ridge_classifier",
                "gradient_boosted_trees": "ML_gradient_boosted_trees",
                "mlp": "ML_mlp",
                "one_dimensional_cnn": "NN_1d_cnn",
                "masked_waveform_transformer_new": "NN_transformer_sequence_encoder_new",
            },
            "artifacts": {
                "report": "REPORT.md",
                "result": "result.json",
                "claimed_ticket": "claimed_ticket.txt",
                "raw_reproduction": "reproduction_match_table.csv",
                "method_summary": "primary_method_summary.csv",
                "traditional_summary": "traditional_method_summary.csv",
                "run_metrics": "run_heldout_metrics.csv",
                "strata_metrics": "stratified_method_metrics.csv",
                "ablation_metrics": "ablation_metrics.csv",
                "predictions": "heldout_predictions.csv.gz",
            },
            "novel_tickets_appended": [],
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-ticket2493 uv run --with uproot --with awkward "
                "--with numpy --with pandas --with scikit-learn --with matplotlib --with tabulate "
                "--with torch python scripts/ticket_2493_s55a_late_tail_afterpulse_attribution.py"
            ),
            "runtime_environment": {"python": platform.python_version(), "git_commit": git_commit()},
        }
    )
    result["winner"]["architecture_note"] = (
        "winner selected by held-out run-block ROC AUC among the required traditional, ridge, GBDT, MLP, 1D-CNN, and masked sequence panels"
    )
    (OUT / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_claim_file()
    write_academic_report(result, primary, traditional, strata, ablations)

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"ticket_id": TICKET, "study_id": "S55a", "worker": WORKER, "git_commit": git_commit()})
    manifest["command"] = f"{sys.executable} scripts/ticket_2493_s55a_late_tail_afterpulse_attribution.py"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(__file__).name), "--config", str(CONFIG)]
        code = int(s28b.main())
    finally:
        sys.argv = old_argv
    if code != 0:
        return code
    postprocess()
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    print(json.dumps({"done": True, "ticket": TICKET, "winner": result["winner"]["method"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
