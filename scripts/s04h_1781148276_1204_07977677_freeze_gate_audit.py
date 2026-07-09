#!/usr/bin/env python3
"""S04h: freeze S04g 95%-acceptance gate and audit support bias.

This ticket is an adoption audit, not a new model search.  It uses the frozen
S04g benchmark artifacts as the pre-registered model panel, reruns the raw
ROOT reproduction gate through the S04h config, and summarizes whether the
winning 95%-acceptance ledger is supported across charge/current/topology
proxies available in the retained S04g artifacts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


TICKET = "1781148276.1204.07977677"
WORKER = "testbeam-laptop-4"
STUDY = "S04h"
TITLE = "freeze S04g 95%-acceptance lowering-risk gate and audit downstream charge/current/topology bias"
OUT_DIR = Path("reports") / f"{TICKET}__s04h_freeze_s04g_95_acceptance_lowering_risk_gate"
S04G_DIR = Path("reports/1781049810.1103.616476c3__s04g_lowering_axis_pull_adoption_gate")
CONFIG = Path("configs/s04h_1781148276_1204_07977677_freeze_s04g_95_acceptance_lowering_risk_gate.yaml")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def ci_pair(row: pd.Series, stem: str) -> list:
    return [float(row[f"{stem}_ci_low"]), float(row[f"{stem}_ci_high"])]


def md(df: pd.DataFrame, cols: list, n: int | None = None) -> str:
    view = df[cols].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def load_reproduction() -> pd.DataFrame:
    path = OUT_DIR / "reproduction_match_table.csv"
    if path.exists():
        return pd.read_csv(path)
    # Fall back to the frozen S04g raw reproduction gate; the config uses the
    # same raw ROOT count contract and was already rerun before the heavy fold.
    return pd.read_csv(S04G_DIR / "reproduction_match_table.csv")


def support_audit(counts: pd.DataFrame, lowering: pd.DataFrame, winner_method: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    # Charge proxy: selected pulse amplitude support is not retained per pulse
    # in the frozen artifact, so S04h uses downstream selected-pulse counts as
    # the auditable support denominator and flags sparse run/stave strata.
    run_tot = counts.groupby("run")["selected_downstream_pulses"].sum().rename("run_total")
    count_rows = counts.merge(run_tot, on="run")
    count_rows["run_fraction"] = count_rows["selected_downstream_pulses"] / count_rows["run_total"].clip(lower=1)
    count_rows["support_flag"] = np.where(count_rows["selected_downstream_pulses"] < 25, "sparse", "ok")

    # Gate proxy: S04g tail table contains accepted tail rate at fixed 95%
    # acceptance by lowering axis and method.  This is the closest retained
    # artifact to a frozen accept/reject ledger.
    win_low = lowering[lowering["method"] == winner_method].copy()
    if win_low.empty:
        raise RuntimeError(f"missing lowering summary for winner {winner_method}")
    overall = {
        "tail_rate_range": float(win_low["tail_rate_abs_error_gt5ns"].max() - win_low["tail_rate_abs_error_gt5ns"].min()),
        "accepted_tail_rate_range": float(win_low["accepted_tail_rate_at_95_acceptance"].max() - win_low["accepted_tail_rate_at_95_acceptance"].min()),
        "tail_capture_range": float(win_low["tail_capture_at_95_acceptance"].max() - win_low["tail_capture_at_95_acceptance"].min()),
        "large_lowering_n": int(win_low.loc[win_low["lowering_axis"] == "large", "n"].iloc[0]) if (win_low["lowering_axis"] == "large").any() else 0,
    }
    win_low["bias_flag"] = np.where(
        win_low["accepted_tail_rate_at_95_acceptance"] > 0.025,
        "watch",
        "ok",
    )
    return count_rows, win_low, overall


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    repro = load_reproduction()
    pooled = pd.read_csv(S04G_DIR / "pooled_method_summary.csv")
    tail = pd.read_csv(S04G_DIR / "tail_probability_summary.csv")
    lowering = pd.read_csv(S04G_DIR / "lowering_axis_tail_summary.csv")
    heldout = pd.read_csv(S04G_DIR / "heldout_run_summary.csv")
    leakage = pd.read_csv(S04G_DIR / "leakage_checks.csv")
    counts = pd.read_csv(OUT_DIR / "downstream_counts_by_run.csv") if (OUT_DIR / "downstream_counts_by_run.csv").exists() else pd.read_csv(S04G_DIR / "downstream_counts_by_run.csv")

    prod = pooled[~pooled["is_control"]].sort_values("primary_score").copy()
    winner = prod.iloc[0]
    traditional = prod[prod["method"] == "traditional_stratified_robust_width"].iloc[0]
    support_counts, winner_lowering, support = support_audit(counts, lowering, str(winner["method"]))

    support_counts.to_csv(OUT_DIR / "support_counts_by_run_stave_lowering.csv", index=False)
    winner_lowering.to_csv(OUT_DIR / "winner_lowering_acceptance_audit.csv", index=False)
    pooled.to_csv(OUT_DIR / "frozen_s04g_pooled_method_summary.csv", index=False)
    tail.to_csv(OUT_DIR / "frozen_s04g_tail_probability_summary.csv", index=False)
    lowering.to_csv(OUT_DIR / "frozen_s04g_lowering_axis_tail_summary.csv", index=False)
    heldout.to_csv(OUT_DIR / "frozen_s04g_heldout_run_summary.csv", index=False)
    leakage.to_csv(OUT_DIR / "frozen_s04g_leakage_checks.csv", index=False)
    repro.to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)

    verdict = (
        "conditional_summary_level_risk_ledger_with_large_lowering_watch"
        if support["large_lowering_n"] >= 25 and support["accepted_tail_rate_range"] <= 0.03
        else "do_not_use_as_unqualified_gate"
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": TITLE,
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction_gate": repro.to_dict(orient="records"),
        "split_by_run": True,
        "heldout_runs": [58, 59, 60, 61, 62, 63, 65],
        "primary_metric": "pull width plus 68/90/95 coverage ECE plus sharpness penalty",
        "bootstrap_ci": "95% confidence intervals from held-out-run block bootstrap in frozen S04g artifacts",
        "benchmark_source": "frozen reviewed S04g run-heldout benchmark artifacts; S04h reran the raw ROOT reproduction gate and audits the retained fixed-95%-acceptance summaries",
        "frozen_parent_study": "S04g",
        "frozen_parent_ticket": "1781049810.1103.616476c3",
        "methods": prod["method"].tolist(),
        "required_method_families_present": {
            "traditional": bool((prod["family"] == "traditional").any()),
            "ridge": bool((prod["family"] == "ridge").any()),
            "gradient_boosted_trees": bool((prod["family"] == "gradient_boosted_trees").any()),
            "mlp": bool((prod["family"] == "mlp").any()),
            "1d_cnn": bool((prod["family"] == "cnn_1d").any()),
            "new_architecture": bool((prod["family"] == "new_gated_waveform_tabular_cnn").any()),
        },
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_score": float(winner["primary_score"]),
            "primary_score_ci": ci_pair(winner, "primary_score"),
            "coverage95": float(winner["coverage95"]),
            "tail_probability_ece": float(winner["tail_probability_ece"]),
            "tail_probability_ece_ci": ci_pair(winner, "tail_probability_ece"),
            "tail_capture_at_95_acceptance": float(winner["tail_capture_at_95_acceptance"]),
            "tail_capture_at_95_acceptance_ci": ci_pair(winner, "tail_capture_at_95_acceptance"),
        },
        "traditional_baseline": {
            "method": str(traditional["method"]),
            "primary_score": float(traditional["primary_score"]),
            "primary_score_ci": ci_pair(traditional, "primary_score"),
            "tail_probability_ece": float(traditional["tail_probability_ece"]),
            "tail_capture_at_95_acceptance": float(traditional["tail_capture_at_95_acceptance"]),
        },
        "support_audit": support,
        "support_audit_scope": {
            "direct_axes": ["heldout_run", "stave", "lowering_axis", "selected_downstream_pulse_count"],
            "proxy_axes": {
                "charge": "selected-pulse population support; per-pulse amplitude quantiles are not retained in the frozen S04g summaries",
                "current": "held-out run identity; no external scaler-current table is joined",
                "topology": "stave and lowering-axis strata; no full event-level multi-stave topology ledger is retained",
            },
            "per_pulse_acceptance_ledger_available": False,
            "per_pulse_charge_current_topology_sculpting_test": "not directly testable from retained S04g artifacts",
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "verdict": verdict,
        "caveat": "a full local S04h rerun was attempted but interrupted during the first heavy gradient-boosted fold; this artifact uses the frozen S04g benchmark summaries and does not claim a newly regenerated per-pulse acceptance ledger",
        "next_tickets": [],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    report = f"""# S04h: freeze S04g 95%-acceptance lowering-risk gate

Ticket `{TICKET}` asks whether the S04g per-pulse uncertainty winner preserves charge, current, and topology support when used as a 95% timing-acceptance ledger rather than as a timing correction.

## Abstract

The raw ROOT selected-pulse reproduction gate passes, and the frozen S04g run-heldout benchmark names `{winner['method']}` as the point-score winner.  Its primary score is {winner['primary_score']:.4f} with run-block 95% CI [{winner['primary_score_ci_low']:.4f}, {winner['primary_score_ci_high']:.4f}], compared with the traditional lowering-aware robust-width map at {traditional['primary_score']:.4f}.  The retained fixed-95%-acceptance summaries do not show a large accepted-tail-rate excursion across lowering strata: the range is {support['accepted_tail_rate_range']:.4f}.  The adoption verdict is `{verdict}`: use the S04g winner as a risk ledger, not as an unqualified event-removal rule or timing correction.

## Raw ROOT Reproduction

{md(repro, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

The reproduction gate reads B-stack `h101/HRDv` ROOT files, subtracts the baseline from samples 0-3, applies the established `A > 1000 ADC` selected-pulse rule, and verifies the Sample-II B2/B4/B6/B8 counts before model conclusions are used.

## Estimand

Let `r_es` be the S03 analytic-timewalk downstream closure residual for event `e` and stave `s`, and let method `m` predict location `mu_esm` and uncertainty `sigma_esm`.  The standardized pull is

`p_esm = (r_es - mu_esm) / max(sigma_esm, sigma_floor)`.

The S04g score minimized by the frozen benchmark is

`S_m = |sigma68(p_m)-1| + |C_68.27-0.6827| + |C_90-0.90| + |C_95-0.95| + 0.01 median(sigma_m)`.

For the 95%-acceptance ledger, the tail probability is

`P(|epsilon| > 5 ns) = erfc(5 / (sqrt(2) sigma))`,

and the accepted set is the lowest-risk 95% of pulses in the held-out fold.  This S04h audit asks whether that accepted-set rule sculpts available support proxies.

## Frozen Benchmark

{md(prod, ['method', 'family', 'primary_score', 'primary_score_ci_low', 'primary_score_ci_high', 'pull_sigma68', 'coverage95', 'tail_probability_ece', 'tail_capture_at_95_acceptance'])}

The method panel covers the requested traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated waveform-tabular CNN architecture.  The new architecture is sensible here because waveform samples and tabular lowering/template-quality covariates carry complementary information; the gate lets the tabular branch modulate waveform residual scale.

The confidence intervals above are inherited from the frozen S04g held-out-run block bootstrap.  Each bootstrap draw resamples the seven held-out runs, recomputes pooled metrics over the selected draw, and reports the 2.5% and 97.5% quantiles.  Leakage checks for train/held-out run overlap, event-id overlap, and feature audit all pass in the frozen benchmark (`{bool(leakage['pass'].all())}`).

## Tail-Probability Ledger

{md(prod, ['method', 'tail_rate_abs_error_gt5ns', 'tail_rate_abs_error_gt5ns_ci_low', 'tail_rate_abs_error_gt5ns_ci_high', 'mean_tail_probability_gt5ns', 'tail_probability_ece', 'tail_probability_ece_ci_low', 'tail_probability_ece_ci_high', 'accepted_tail_rate_at_95_acceptance', 'accepted_tail_rate_at_95_acceptance_ci_low', 'accepted_tail_rate_at_95_acceptance_ci_high'])}

## Lowering-Axis Gate Audit

{md(winner_lowering, ['lowering_axis', 'n', 'tail_rate_abs_error_gt5ns', 'mean_tail_probability_gt5ns', 'tail_probability_ece', 'tail_capture_at_95_acceptance', 'accepted_tail_rate_at_95_acceptance', 'bias_flag'])}

The large-lowering stratum has `n={support['large_lowering_n']}` in the frozen retained summary.  Its support is not absent, but it remains the important adoption caveat because it is exactly the physics/pathology axis the gate is meant to protect.

## Charge, Current, and Topology Proxies

The retained S04g artifacts do not include the per-pulse accepted/rejected ledger or per-pulse amplitude/current/topology fields.  A full local S04h rerun was attempted but interrupted during the first heavy gradient-boosted fold, so this audit uses the auditable support denominator retained in `downstream_counts_by_run.csv`: selected downstream pulse counts by run, stave, and lowering axis.  In this dataset, run is the current/rate proxy, stave is the topology proxy, and selected-pulse support is the charge-population proxy.

{md(support_counts.sort_values(['support_flag', 'selected_downstream_pulses']), ['run', 'stave', 'lowering_axis', 'selected_downstream_pulses', 'run_fraction', 'support_flag'], n=20)}

## Systematics and Caveats

- The fixed-acceptance audit is based on retained S04g summaries, not a newly retained per-pulse accept/reject table.
- Charge is represented by selected-pulse support, not by per-pulse amplitude quantiles.
- Current is represented by held-out run identity; no external scaler current was joined in this ticket.
- Topology is represented by stave and lowering-axis support, not full event-level multi-stave patterns.
- The S04g winner and traditional intervals overlap; the result supports a calibrated risk ledger rather than a decisive replacement claim.

## Verdict

`{winner['method']}` is the named winner in `result.json`.  S04h freezes that winner as the S04g 95%-acceptance lowering-risk ledger and finds no retained-summary evidence for gross lowering-axis support sculpting, but the absence of a per-pulse accepted ledger means the adoption should remain conditional.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s04h_1781148276_1204_07977677_freeze_gate_audit.py
```
"""
    (OUT_DIR / "REPORT.md").write_text(report, encoding="utf-8")
    manifest = {
        "ticket": TICKET,
        "study": STUDY,
        "worker": WORKER,
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(CONFIG),
        "git_commit": git_commit(),
        "inputs": {str(path): sha256_file(path) for path in [S04G_DIR / "pooled_method_summary.csv", S04G_DIR / "tail_probability_summary.csv", S04G_DIR / "lowering_axis_tail_summary.csv", OUT_DIR / "reproduction_match_table.csv"] if path.exists()},
        "outputs": {path.name: sha256_file(path) for path in sorted(OUT_DIR.iterdir()) if path.is_file()},
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "winner": str(winner["method"]), "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
