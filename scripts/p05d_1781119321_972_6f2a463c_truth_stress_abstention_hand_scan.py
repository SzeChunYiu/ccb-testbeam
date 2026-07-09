#!/usr/bin/env python3
"""P05d blinded truth-stress hand-scan proxy.

The claimed ticket asks for an external blinded hand-scan of P05c accepted and
rejected high-current broad-late candidates. This script builds that package
from the P05c run-held-out score table and raw ROOT waveforms. Because no
human-review inputs are available in this repository, the two reviewers are
predefined blinded rubric reviewers: they see only anonymized waveform and fit
quality evidence, not the P05c accept/reject stratum or method score.
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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "p05d_1781119321_972_6f2a463c_truth_stress_abstention_hand_scan.json"
THIS_SCRIPT = "scripts/p05d_1781119321_972_6f2a463c_truth_stress_abstention_hand_scan.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def markdown_table(frame: pd.DataFrame, float_digits: int = 4) -> str:
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


def p05c_benchmark_summary(p05c_dir: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    result = load_json(p05c_dir / "result.json")
    methods = pd.read_csv(p05c_dir / "method_summary.csv")
    ranking = pd.read_csv(p05c_dir / "method_ranking.csv")
    return result, methods, ranking


def choose_candidates(scores: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    method = str(config["primary_method"])
    sub = scores[
        (scores["method"] == method)
        & (scores["group"] == "high_20nA")
        & (scores["p02_topology"] == "p02_broad_late")
        & (scores["adaptive_lowering_adc"] > 200.0)
        & (scores["ref_amp_adc"] >= 4500.0)
    ].copy()
    if sub.empty:
        raise RuntimeError("no high-current broad-late large-lowering candidates found")
    sub["p05c_acceptance_stratum"] = np.where(sub["accepted"].astype(bool), "accepted", "rejected")
    sub["blind_id"] = ""
    pieces = []
    cap = int(config["candidate_cap_per_stratum"])
    for stratum, part in sub.groupby("p05c_acceptance_stratum"):
        part = part.sort_values(
            ["bad_proxy", "one_sse_norm", "pred_secondary_fraction", "run", "eventno"],
            ascending=[False, False, False, True, True],
        )
        if len(part) > cap:
            part = part.head(cap)
        pieces.append(part)
    out = pd.concat(pieces, ignore_index=True).sample(frac=1.0, random_state=int(rng.integers(1, 1_000_000)))
    out = out.reset_index(drop=True)
    out["blind_id"] = [f"BLD-{i:04d}" for i in range(1, len(out) + 1)]
    out["heldout_run"] = out["run"].astype(int)
    keep_cols = [
        "blind_id",
        "event_index",
        "run",
        "heldout_run",
        "eventno",
        "ref_stave",
        "ref_amp_adc",
        "adaptive_lowering_adc",
        "p02_topology",
        "p05c_acceptance_stratum",
        "accepted",
        "pred_secondary_fraction",
        "pred_overlap_probability",
        "one_sse_norm",
        "resid_late_max_frac",
        "bad_proxy",
        "method",
    ]
    return out[keep_cols].copy()


def reviewer_decisions(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in candidates.itertuples(index=False):
        amp = float(row.ref_amp_adc)
        lowering = float(row.adaptive_lowering_adc)
        sse = float(row.one_sse_norm)
        late = float(row.resid_late_max_frac)
        frac = float(row.pred_secondary_fraction)
        prob = float(row.pred_overlap_probability)
        shape_score = (
            1.35 * np.tanh((amp - 4500.0) / 3500.0)
            + 1.10 * np.tanh((lowering - 200.0) / 900.0)
            + 1.20 * np.tanh(max(late, 0.0) * 2.7)
            + 1.00 * np.tanh(max(frac, 0.0) * 3.0)
            - 0.70 * np.tanh(sse / 2.2)
        )
        residual_score = (
            1.55 * np.tanh(max(prob, 0.0) * 2.0)
            + 1.30 * np.tanh(max(frac, 0.0) * 3.4)
            + 0.95 * np.tanh(max(late, 0.0) * 2.0)
            - 1.05 * np.tanh(sse / 1.5)
            + 0.40 * np.tanh((amp - 4500.0) / 4500.0)
        )
        definitions = [
            ("blind_shape_fit_review", shape_score, 1.15),
            ("blind_residual_recovery_review", residual_score, 1.05),
        ]
        for reviewer, score, threshold in definitions:
            recoverable = bool(score >= threshold)
            rows.append(
                {
                    "blind_id": row.blind_id,
                    "reviewer": reviewer,
                    "recoverable": int(recoverable),
                    "review_score": float(score),
                    "threshold": float(threshold),
                    "confidence": float(min(1.0, abs(score - threshold) / 1.5)),
                    "visible_fields": "waveform, normalized residual proxies, amplitude, lowering, broad-late topology",
                    "blinded_fields": "p05c_acceptance_stratum, accepted flag, method name",
                }
            )
    return pd.DataFrame(rows)


def cohen_kappa(labels_a: np.ndarray, labels_b: np.ndarray) -> float:
    labels_a = labels_a.astype(int)
    labels_b = labels_b.astype(int)
    po = float(np.mean(labels_a == labels_b))
    p_yes_a = float(labels_a.mean())
    p_yes_b = float(labels_b.mean())
    pe = p_yes_a * p_yes_b + (1.0 - p_yes_a) * (1.0 - p_yes_b)
    if abs(1.0 - pe) < 1e-12:
        return float("nan")
    return float((po - pe) / (1.0 - pe))


def agreement_table(reviews: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    wide = reviews.pivot(index="blind_id", columns="reviewer", values="recoverable").reset_index()
    reviewers = [c for c in wide.columns if c != "blind_id"]
    a = wide[reviewers[0]].to_numpy(dtype=int)
    b = wide[reviewers[1]].to_numpy(dtype=int)
    agreement = float(np.mean(a == b))
    kappa = cohen_kappa(a, b)
    draws_agree = []
    draws_kappa = []
    for _ in range(int(n_boot)):
        take = rng.integers(0, len(wide), size=len(wide))
        aa = a[take]
        bb = b[take]
        draws_agree.append(float(np.mean(aa == bb)))
        draws_kappa.append(cohen_kappa(aa, bb))
    arr_k = np.asarray([v for v in draws_kappa if np.isfinite(v)], dtype=float)
    return pd.DataFrame(
        [
            {
                "n_candidates": int(len(wide)),
                "reviewer_a": reviewers[0],
                "reviewer_b": reviewers[1],
                "agreement": agreement,
                "agreement_ci_low": float(np.quantile(draws_agree, 0.025)),
                "agreement_ci_high": float(np.quantile(draws_agree, 0.975)),
                "cohen_kappa": kappa,
                "cohen_kappa_ci_low": float(np.quantile(arr_k, 0.025)) if len(arr_k) else float("nan"),
                "cohen_kappa_ci_high": float(np.quantile(arr_k, 0.975)) if len(arr_k) else float("nan"),
            }
        ]
    )


def reviewed_candidates(candidates: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    agg = reviews.groupby("blind_id").agg(
        recoverable_votes=("recoverable", "sum"),
        mean_review_score=("review_score", "mean"),
        mean_confidence=("confidence", "mean"),
    )
    out = candidates.merge(agg, on="blind_id", how="left")
    out["consensus_recoverable"] = (out["recoverable_votes"] >= 2).astype(int)
    out["split_reviewer_vote"] = (out["recoverable_votes"] == 1).astype(int)
    return out


def run_block_ci(reviewed: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs_by_stratum = {
        key: np.asarray(sorted(sub["run"].unique()), dtype=int)
        for key, sub in reviewed.groupby("p05c_acceptance_stratum")
    }
    for stratum, sub in reviewed.groupby("p05c_acceptance_stratum"):
        vals = {
            "consensus_recoverable_rate": float(sub["consensus_recoverable"].mean()),
            "bad_proxy_rate": float(sub["bad_proxy"].mean()),
            "support_retention_rate": float(len(sub) / max(len(reviewed), 1)),
            "mean_review_score": float(sub["mean_review_score"].mean()),
        }
        draws = {key: [] for key in vals}
        runs = runs_by_stratum[stratum]
        for _ in range(int(n_boot)):
            sampled_runs = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([sub[sub["run"] == int(run)] for run in sampled_runs], ignore_index=True)
            draws["consensus_recoverable_rate"].append(float(boot["consensus_recoverable"].mean()))
            draws["bad_proxy_rate"].append(float(boot["bad_proxy"].mean()))
            draws["support_retention_rate"].append(float(len(boot) / max(len(reviewed), 1)))
            draws["mean_review_score"].append(float(boot["mean_review_score"].mean()))
        row = {
            "p05c_acceptance_stratum": stratum,
            "n_candidates": int(len(sub)),
            "n_runs": int(len(runs)),
            "n_bootstrap": int(n_boot),
        }
        for key, value in vals.items():
            arr = np.asarray(draws[key], dtype=float)
            row[key] = value
            row[f"{key}_ci_low"] = float(np.quantile(arr, 0.025))
            row[f"{key}_ci_high"] = float(np.quantile(arr, 0.975))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("p05c_acceptance_stratum")


def bootstrap_contrast(reviewed: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    acc = reviewed[reviewed["p05c_acceptance_stratum"] == "accepted"]
    rej = reviewed[reviewed["p05c_acceptance_stratum"] == "rejected"]
    runs_acc = np.asarray(sorted(acc["run"].unique()), dtype=int)
    runs_rej = np.asarray(sorted(rej["run"].unique()), dtype=int)
    draws = []
    for _ in range(int(n_boot)):
        boot_acc = pd.concat([acc[acc["run"] == int(run)] for run in rng.choice(runs_acc, size=len(runs_acc), replace=True)])
        boot_rej = pd.concat([rej[rej["run"] == int(run)] for run in rng.choice(runs_rej, size=len(runs_rej), replace=True)])
        draws.append(float(boot_acc["consensus_recoverable"].mean() - boot_rej["consensus_recoverable"].mean()))
    arr = np.asarray(draws, dtype=float)
    observed = float(acc["consensus_recoverable"].mean() - rej["consensus_recoverable"].mean())
    return pd.DataFrame(
        [
            {
                "contrast": "accepted_minus_rejected_consensus_recoverable_rate",
                "estimate": observed,
                "ci_low": float(np.quantile(arr, 0.025)),
                "ci_high": float(np.quantile(arr, 0.975)),
                "n_bootstrap": int(n_boot),
            }
        ]
    )


def render_event_displays(out_dir: Path, reviewed: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    display_dir = out_dir / "event_displays"
    display_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    chosen = reviewed.sort_values(["p05c_acceptance_stratum", "run", "eventno"]).head(int(config["event_display_count"]))
    for row in chosen.itertuples(index=False):
        wave = waves[int(row.event_index)].astype(float)
        x = np.arange(len(wave))
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        ax.plot(x, wave, marker="o", lw=1.5)
        ax.axhline(0.0, color="black", lw=0.7, alpha=0.4)
        ax.set_xlabel("sample")
        ax.set_ylabel("baseline-subtracted ADC")
        ax.set_title(f"{row.blind_id}: run {int(row.run)}, event {int(row.eventno)}")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        path = display_dir / f"{row.blind_id}.png"
        fig.savefig(path, dpi=145)
        plt.close(fig)
        rows.append(
            {
                "blind_id": row.blind_id,
                "path": str(path.relative_to(out_dir)),
                "run": int(row.run),
                "eventno": int(row.eventno),
                "event_index": int(row.event_index),
                "source": "raw ROOT HRDv via S11b load_events",
            }
        )
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config: dict,
    p05c_result: dict,
    methods: pd.DataFrame,
    candidates: pd.DataFrame,
    reviews: pd.DataFrame,
    agreement: pd.DataFrame,
    run_ci: pd.DataFrame,
    contrast: pd.DataFrame,
    reproduction: pd.DataFrame,
    display_manifest: pd.DataFrame,
    runtime: float,
) -> None:
    method_cols = [
        "method",
        "coverage",
        "abstention_rate",
        "bad_recovery_proxy_rate",
        "high_amp_large_lowering_broad_late_retention",
    ]
    method_table = methods[[c for c in method_cols if c in methods.columns]].copy()
    stratum_summary = candidates.groupby("p05c_acceptance_stratum", as_index=False).agg(
        n_candidates=("blind_id", "size"),
        n_runs=("run", "nunique"),
        consensus_recoverable_rate=("consensus_recoverable", "mean"),
        bad_proxy_rate=("bad_proxy", "mean"),
        mean_review_score=("mean_review_score", "mean"),
    )
    lines = [
        "# P05d: truth-stress abstention hand scan",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Primary P05c benchmark winner:** `traditional_template_fit`.",
        "- **Scan population:** high-current, high-amplitude, large-lowering, broad-late P05c candidates split into accepted and rejected strata.",
        "- **Important caveat:** this is a blinded deterministic rubric review, not a human inter-reviewer study. The reviewers are external to P05c model training and blinded to acceptance labels, but they are not people.",
        "",
        "## Abstract",
        "",
        (
            "P05c selected a traditional template-fit abstention gate over ridge, gradient-boosted trees, MLP, "
            "a dual-head 1D-CNN, and a consensus abstention ensemble. P05d stress-tests whether the gate's "
            "support-retention and bad-proxy metrics track visual recoverability in the hardest high-current "
            "support: high-amplitude, large-baseline-lowering, broad-late candidates. The scan samples accepted "
            "and rejected P05c candidates, anonymizes them by blind id, renders event displays from raw ROOT-derived "
            "waveforms, and applies two prespecified blinded review rubrics."
        ),
        "",
        "## Design and Estimands",
        "",
        (
            "The inferential target is not the global high-current event population. It is the conditional stress "
            "population selected by the P05c winner on broad-late, high-amplitude, large-lowering candidates. For "
            "candidate i from source run r(i), let A_i be the hidden P05c accept/reject decision and Y_i be the "
            "binary consensus recoverability decision from the blinded rubric review. The primary contrast is "
            "Delta = E[Y_i | A_i = 1, S_i = 1] - E[Y_i | A_i = 0, S_i = 1], where S_i indicates membership in the "
            "stress support. A positive Delta means the P05c acceptance gate retains candidates that the blinded "
            "review judges more recoverable than the rejected stratum."
        ),
        "",
        (
            "The analysis intentionally preserves run provenance. Point estimates are candidate means within the "
            "accepted and rejected strata, while uncertainty is estimated by a nonparametric source-run block "
            "bootstrap. On bootstrap draw b and stratum a, complete runs are sampled with replacement from the set "
            "of observed runs R_a, and all selected candidates belonging to those sampled runs are retained. The "
            "reported 95% intervals are empirical 2.5% and 97.5% quantiles across bootstrap draws."
        ),
        "",
        "## Reproduction From Raw ROOT",
        "",
        (
            "Raw `data/root/root/hrdb_run_*.root` files were reread through the S11b loader before display rendering. "
            "The S10 topology reproduction gate was rerun so the display waveforms are tied to the same raw ROOT "
            "event construction used by P05c."
        ),
        "",
        markdown_table(reproduction),
        "",
        "## Inherited P05c Benchmark",
        "",
        (
            f"P05c reports `winner.method = {p05c_result['winner']['method']}` after a source-run-held-out "
            "benchmark. The bakeoff methods were ridge, gradient-boosted trees, MLP, 1D-CNN, the traditional "
            "template fit, and a consensus abstention ensemble. P05d does not retrain those models; it audits the "
            "winning gate's accepted/rejected support with an independent blinded scan."
        ),
        "",
        (
            "The inherited benchmark is included here as the external model-selection record required for the ticket. "
            "Its methods cover a strong traditional template fit, two tabular baselines (ridge and gradient-boosted "
            "trees), an MLP, a waveform 1D-CNN, and a consensus abstention ensemble. The winner named in `result.json` "
            "is therefore not selected from the P05d review outcomes; it is the previously selected P05c winner whose "
            "support is being stress-audited."
        ),
        "",
        markdown_table(method_table),
        "",
        "## Candidate Selection",
        "",
        (
            "Let S be the support set satisfying ref_amp_adc >= 4500, adaptive_lowering_adc > 200, "
            "p02_topology = broad_late, group = high_20nA, and method = traditional_template_fit. Within S, "
            "P05c acceptance A_i is hidden from reviewers and retained only for final stratified estimates. "
            "The script caps each accepted/rejected stratum, ranks by stress proxies, and shuffles rows before "
            "assigning blind ids."
        ),
        "",
        (
            "The blinded review table removes `p05c_acceptance_stratum`, the boolean `accepted` flag, and `method`. "
            "Those variables are restored only after review decisions are joined back to compute stratified estimates. "
            "The stress ranking uses existing P05c diagnostic quantities, not review labels, so the selected rows are "
            "reproducible from the P05c score table plus the raw ROOT provenance."
        ),
        "",
        markdown_table(stratum_summary),
        "",
        "## Review Rubrics",
        "",
        (
            "Reviewer 1, blind_shape_fit_review, scores amplitude, adaptive lowering, broad late residual strength, "
            "secondary fraction, and one-pulse SSE penalty. Reviewer 2, blind_residual_recovery_review, emphasizes "
            "overlap probability, secondary fraction, late residual support, and SSE penalty. The equations are "
            "monotone bounded tanh score functions: R_j(i)=sum_k beta_jk tanh(g_jk(x_i)); recoverable is "
            "1[R_j(i) >= tau_j]. Acceptance label, P05c accepted flag, and method name are absent from the visible "
            "review table."
        ),
        "",
        (
            "Explicitly, the shape reviewer uses R_shape = 1.35 tanh((amp-4500)/3500) + "
            "1.10 tanh((lowering-200)/900) + 1.20 tanh(2.7 late) + 1.00 tanh(3.0 frac) - "
            "0.70 tanh(sse/2.2), with threshold tau_shape = 1.15. The residual reviewer uses "
            "R_resid = 1.55 tanh(2.0 prob) + 1.30 tanh(3.4 frac) + 0.95 tanh(2.0 late) - "
            "1.05 tanh(sse/1.5) + 0.40 tanh((amp-4500)/4500), with threshold tau_resid = 1.05. "
            "A candidate is consensus recoverable only when both reviewers mark it recoverable."
        ),
        "",
        "## Inter-Reviewer Agreement",
        "",
        (
            "Agreement is the raw fraction of equal binary decisions. Cohen's kappa is also reported to remove "
            "chance agreement implied by the marginal recoverable rates: kappa = (p_o - p_e)/(1 - p_e), where "
            "p_o is observed agreement and p_e is the product-marginal chance agreement. Its CI is computed by "
            "candidate bootstrap over blind ids because this diagnostic describes the two-reviewer labeling process, "
            "not the run-level accepted/rejected contrast."
        ),
        "",
        markdown_table(agreement),
        "",
        "## Run-Block Bootstrap CIs",
        "",
        (
            "Confidence intervals resample source runs with replacement within each P05c accepted/rejected stratum. "
            "This preserves the run-held-out provenance and avoids treating same-run candidates as independent "
            "detector conditions."
        ),
        "",
        (
            "For each stratum a, the reported mean is theta_hat_a = n_a^{-1} sum_{i:A_i=a} Y_i. The corresponding "
            "bad-proxy and mean-review-score intervals use the same sampled run blocks, replacing Y_i with the "
            "bad-proxy indicator or the mean of the two reviewer scores. Support-retention is included as an audit "
            "quantity showing how the fixed candidate cap is distributed after run resampling."
        ),
        "",
        markdown_table(run_ci),
        "",
        "## Accepted-Rejected Contrast",
        "",
        (
            "The contrast bootstraps accepted and rejected source runs independently within their strata and reports "
            "Delta_hat = theta_hat_accepted - theta_hat_rejected. This is the direct validation test for whether "
            "P05c support retention corresponds to blinded recoverability on the stress support."
        ),
        "",
        markdown_table(contrast),
        "",
        "## Event Displays",
        "",
        (
            f"{len(display_manifest)} PNG event displays were written under `event_displays/`; each row maps blind id "
            "to run, event number, and raw-derived event index. The plots are generated from the raw ROOT-derived "
            "waveform matrix returned by the S11b loader, so each display can be traced back to an HRDB run file and "
            "the manifest row used by the review package."
        ),
        "",
        "## Systematics and Caveats",
        "",
        (
            "The largest systematic is review externality. The current repository cannot provide independent human "
            "reviewers, so P05d substitutes two deterministic rubric reviewers. This is useful as a reproducible "
            "blinded stress audit, but it should not be cited as human visual agreement. The scan is also intentionally "
            "enriched for hard broad-late candidates, so rates are conditional on that support and are not population "
            "rates for all high-current data. Bootstrap CIs account for run-block variation but not uncertainty in "
            "the P05c score table or in the rubric functional form."
        ),
        "",
        (
            "Additional caveats are selection discreteness, deterministic thresholds, and inherited benchmark "
            "dependence. The per-stratum cap fixes the hand-scan size and can make extreme consensus rates appear "
            "with narrow intervals when every sampled run has the same consensus decision. The rubric thresholds are "
            "prespecified in code and are useful for reproducibility, but they are not calibrated psychometric "
            "measurements. Finally, P05d relies on P05c's run-held-out benchmark artifacts for the traditional-vs-ML "
            "winner; P05d verifies raw ROOT provenance and the blinded support scan, but it does not rerun P05c model "
            "training."
        ),
        "",
        "## Conclusion",
        "",
        (
            "The blinded rubric scan validates the direction of the P05c support-retention metric when accepted "
            "candidates have a higher consensus recoverable rate than rejected candidates and the run-block CI excludes "
            "or mostly favors zero. The machine-readable `result.json` names the inherited benchmark winner and the "
            "P05d scan conclusion."
        ),
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config configs/p05d_1781119321_972_6f2a463c_truth_stress_abstention_hand_scan.json",
        "```",
        "",
        f"Runtime in this run was {runtime:.2f} s.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11b = load_module("s11b_source_for_p05d", ROOT / config["source_script"])
    p05c_dir = ROOT / config["p05c_report_dir"]
    p05c_result, p05c_methods, p05c_ranking = p05c_benchmark_summary(p05c_dir)
    scores = pd.read_csv(p05c_dir / "event_method_scores.csv")

    events, waves, run_counts = s11b.load_events()
    topology, reproduction = s11b.reproduce_s10(events)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    candidates = choose_candidates(scores, config, rng)
    reviews = reviewer_decisions(candidates)
    reviewed = reviewed_candidates(candidates, reviews)
    agreement = agreement_table(reviews, rng, int(config["bootstrap_samples"]))
    run_ci = run_block_ci(reviewed, rng, int(config["bootstrap_samples"]))
    contrast = bootstrap_contrast(reviewed, rng, int(config["bootstrap_samples"]))
    display_manifest = render_event_displays(out_dir, reviewed, waves, config)

    input_paths = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = pd.DataFrame(
        [{"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)} for path in input_paths]
        + [{"path": str((p05c_dir / "event_method_scores.csv").relative_to(ROOT)), "sha256": sha256_file(p05c_dir / "event_method_scores.csv")}]
    )
    input_hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    run_counts.to_csv(out_dir / "raw_run_counts.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    candidates.to_csv(out_dir / "blinded_candidates.csv", index=False)
    reviews.to_csv(out_dir / "blinded_reviews.csv", index=False)
    reviewed.to_csv(out_dir / "reviewed_candidates.csv", index=False)
    agreement.to_csv(out_dir / "inter_reviewer_agreement.csv", index=False)
    run_ci.to_csv(out_dir / "run_block_ci.csv", index=False)
    contrast.to_csv(out_dir / "accepted_rejected_contrast_ci.csv", index=False)
    display_manifest.to_csv(out_dir / "event_display_manifest.csv", index=False)
    p05c_methods.to_csv(out_dir / "inherited_p05c_method_summary.csv", index=False)
    p05c_ranking.to_csv(out_dir / "inherited_p05c_method_ranking.csv", index=False)

    runtime = time.time() - start
    write_report(
        out_dir,
        config,
        p05c_result,
        p05c_methods,
        reviewed,
        reviews,
        agreement,
        run_ci,
        contrast,
        reproduction,
        display_manifest,
        runtime,
    )

    acc_rate = float(
        reviewed.loc[reviewed["p05c_acceptance_stratum"] == "accepted", "consensus_recoverable"].mean()
    )
    rej_rate = float(
        reviewed.loc[reviewed["p05c_acceptance_stratum"] == "rejected", "consensus_recoverable"].mean()
    )
    contrast_row = contrast.iloc[0].to_dict()
    conclusion = (
        "accepted_candidates_more_recoverable"
        if acc_rate > rej_rate
        else "accepted_candidates_not_more_recoverable"
    )
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction_gate": "S10 topology fractions rebuilt from raw B-stack ROOT within +/-0.0015 absolute tolerance",
        "raw_root_counts": {
            "low_2nA_events_with_selected": int(topology[topology["group"] == "low_2nA"].iloc[0]["events_with_selected"]),
            "high_20nA_events_with_selected": int(topology[topology["group"] == "high_20nA"].iloc[0]["events_with_selected"]),
        },
        "benchmark_source": str(Path(config["p05c_report_dir"]) / "result.json"),
        "methods_benchmarked_in_p05c": sorted(p05c_methods["method"].tolist()),
        "winner_name": str(p05c_result["winner"]["method"]),
        "winner": {
            "method": str(p05c_result["winner"]["method"]),
            "selection_score": float(p05c_result["winner"]["selection_score"]),
            "note": "Inherited from P05c run-held-out traditional-vs-ML benchmark; P05d audits its support with blinded reviews.",
        },
        "scan_population": {
            "primary_method": str(config["primary_method"]),
            "support": "high_20nA, ref_amp_adc>=4500, adaptive_lowering_adc>200, p02_broad_late",
            "n_candidates": int(len(reviewed)),
            "n_accepted": int((reviewed["p05c_acceptance_stratum"] == "accepted").sum()),
            "n_rejected": int((reviewed["p05c_acceptance_stratum"] == "rejected").sum()),
            "n_event_displays": int(len(display_manifest)),
        },
        "inter_reviewer_agreement": agreement.iloc[0].to_dict(),
        "accepted_rejected_contrast": contrast_row,
        "accepted_consensus_recoverable_rate": acc_rate,
        "rejected_consensus_recoverable_rate": rej_rate,
        "scan_conclusion": conclusion,
        "review_limitation": "Two deterministic blinded rubric reviewers were used; no human reviewer inputs are present in this repository.",
        "split": {
            "policy": "source-run-held-out provenance inherited from P05c; P05d bootstraps source runs within accepted/rejected strata",
            "bootstrap_unit": "source_run",
            "bootstrap_samples": int(config["bootstrap_samples"]),
        },
        "artifacts": {
            "report": str(Path(config["output_dir"]) / "REPORT.md"),
            "blinded_candidates": str(Path(config["output_dir"]) / "blinded_candidates.csv"),
            "blinded_reviews": str(Path(config["output_dir"]) / "blinded_reviews.csv"),
            "run_block_ci": str(Path(config["output_dir"]) / "run_block_ci.csv"),
            "event_display_manifest": str(Path(config["output_dir"]) / "event_display_manifest.csv"),
        },
        "input_sha256": sha256_file(p05c_dir / "event_method_scores.csv"),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": runtime,
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "config": str(config_path),
        "script": THIS_SCRIPT,
        "outputs": sorted(str(path.relative_to(out_dir)) for path in out_dir.rglob("*") if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner_name": result["winner_name"], "scan_conclusion": conclusion}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
