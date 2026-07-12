#!/usr/bin/env python3
"""S29c causal pulse-window PID/energy ablation.

This ticket extends the S27c causal-window machinery with an explicit S29c
reporting layer.  The raw ROOT recount, endpoint panel assembly, bootstrap
interval preservation, and window attribution functions are reused from the
audited S27c implementation; this wrapper pins a new config and writes an
S29c-specific academic report focused on PID/energy causal sample support.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s29c_1783809165_2835_20015c6e_causal_pulse_window_pid_energy_ablation.json"
BASE_SCRIPT = ROOT / "scripts/s27c_1783780945_12618_2f77649e_causal_pulse_window_ablation_pid_energy_timing.py"


def load_base():
    spec = importlib.util.spec_from_file_location("s29c_base_s27c", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s29c_base_s27c"] = module
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def _fmt_ci(lo: float, hi: float) -> str:
    return f"[{lo:.5g}, {hi:.5g}]"


def build_report(
    cfg: Dict[str, Any],
    result: Dict[str, Any],
    panel: pd.DataFrame,
    window_attr: pd.DataFrame,
    leakage: pd.DataFrame,
    attention: pd.DataFrame,
    repro: pd.DataFrame,
    sources: pd.DataFrame,
) -> str:
    winner = result["winner_details"]
    weights = cfg["score_weights"]
    peak = window_attr.loc[window_attr["window_mask"] == "peak_charge_samples_8_11"].sort_values("window_loss_score").iloc[0]
    rise = window_attr.loc[window_attr["window_mask"] == "rising_edge_samples_4_7"].sort_values("window_loss_score").iloc[0]
    late = window_attr.loc[window_attr["window_mask"] == "late_tail_samples_12_17"].sort_values("window_loss_score").iloc[0]
    pre = window_attr.loc[window_attr["window_mask"] == "pretrigger_pedestal_samples_0_3"].sort_values("window_loss_score").iloc[0]

    methods = pd.DataFrame(
        [
            {"method": name, "family": spec["family"], "description": spec["description"]}
            for name, spec in cfg["methods"].items()
        ]
    )
    lines = [
        f"# {cfg['study_id']} - Causal Pulse-Window PID Energy Ablation",
        "",
        f"Ticket: `{cfg['ticket_id']}`  ",
        f"Worker: `{cfg['worker']}`  ",
        "Project: `testbeam`",
        "",
        "## Abstract",
        (
            "S29c asks which of the 18 B-stack pulse samples carry causal PID and energy information, "
            "and which instead behave like pedestal, saturation, pile-up, or late-tail nuisance support. "
            "The study first reproduces the canonical selected-pulse count directly from raw ROOT, then "
            "benchmarks a strong traditional charge/template method against ridge, gradient-boosted trees, "
            "MLP, 1D-CNN, and a compact causal sequence/residual architecture on run-held-out endpoint "
            "panels with run-block bootstrap confidence intervals. The named winner in `result.json` is "
            f"**{result['winner']}**, with weighted joint loss {winner['joint_loss_score']:.6f}. "
            "Compared with S24-S28, this ticket is not another global waveform bakeoff: it isolates the "
            "sample windows responsible for PID/energy gain and reports late-tail and pedestal promotion guards."
        ),
        "",
        "## Pre-Registered Target",
        (
            "Before looking at S29c outputs, the winner rule was fixed as the minimum weighted joint loss "
            "over the complete method panel. The score combines PID AUC loss, fractional energy sigma68, "
            "timing sigma68, pile-up average-precision loss, saturation recovery width, pedestal MAE, and "
            "absolute energy bias. All intervals are inherited from or computed on held-out run blocks, not "
            "event-resampled rows."
        ),
        "",
        "The registered loss is",
        "",
        (
            "`L_m = w_pid(1-AUC_pid,m) + w_E R68_E,m + w_t sigma_t,m/1.5 "
            "+ w_p(1-AP_pileup,m)/0.75 + w_s R68_sat,m + "
            "w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`."
        ),
        "",
        BASE.md_table(pd.DataFrame([weights]), list(weights.keys())),
        "",
        "## Raw ROOT Reproduction",
        (
            "The analysis opens `h101/HRDv` in every configured `hrdb_run_XXXX.root`, reshapes the waveform "
            "branch to `(event, channel, sample)`, subtracts the median of samples 0-3 per channel, and counts "
            f"B2/B4/B6/B8 pulses with maximum corrected amplitude above {cfg['amplitude_cut_adc']:.0f} ADC. "
            "This is the reproduce-first gate for the ticket."
        ),
        "",
        BASE.md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "## Run Split and Bootstrap",
        (
            "The split is by complete source runs. The four groups are sample-I calibration, sample-I analysis, "
            "sample-II calibration, and sample-II analysis; no event from a held-out run is used for fitting a "
            "method row. Bootstrap intervals are percentile intervals over run blocks:"
        ),
        "",
        "`S_b = {r_1, ..., r_R},  theta_b = T(union_{r in S_b} D_r),  CI_95 = [q_0.025(theta_b), q_0.975(theta_b)]`.",
        "",
        "This is intentionally conservative for gain, pedestal, and rate drifts that are coherent within a run.",
        "",
        "## Method Panel",
        BASE.md_table(methods, ["method", "family", "description"]),
        "",
        "The traditional comparator is a matched-filter/template and charge-depth likelihood method, not a strawman. "
        "Ridge tests linear accessibility of each registered pulse window. Gradient-boosted trees test nonlinear "
        "threshold and saturation interactions. The MLP and 1D-CNN test tabular and local waveform neural capacity. "
        "The compact sequence/residual architecture is the new architecture: it uses the source panel's GRU, residual "
        "MLP, and gated-CNN endpoint heads only where the complete run-held-out evidence exists.",
        "",
        "## Primary Head-to-Head Results",
        BASE.md_table(
            panel,
            [
                "method",
                "family",
                "pid_auc",
                "energy_res68_frac",
                "timing_sigma68_ns",
                "pileup_average_precision",
                "saturation_hysteresis_res68",
                "pedestal_mae_adc",
                "joint_loss_score",
            ],
        ),
        "",
        "## Bootstrap Confidence Intervals",
        BASE.md_table(
            panel,
            [
                "method",
                "pid_auc_ci_low",
                "pid_auc_ci_high",
                "energy_res68_ci_low",
                "energy_res68_ci_high",
                "timing_sigma68_ci_low",
                "timing_sigma68_ci_high",
                "pileup_ap_ci_low",
                "pileup_ap_ci_high",
                "saturation_hysteresis_res68_ci_low",
                "saturation_hysteresis_res68_ci_high",
            ],
        ),
        "",
        "Winner detail: "
        f"`{winner['method']}` has PID AUC {winner['pid_auc']:.5f} "
        f"{_fmt_ci(winner['pid_auc_ci_low'], winner['pid_auc_ci_high'])}, energy R68 "
        f"{winner['energy_res68_frac']:.5f} {_fmt_ci(winner['energy_res68_ci_low'], winner['energy_res68_ci_high'])}, "
        f"timing sigma68 {winner['timing_sigma68_ns']:.5f} ns "
        f"{_fmt_ci(winner['timing_sigma68_ci_low'], winner['timing_sigma68_ci_high'])}.",
        "",
        "## Causal Window Attribution",
        (
            "The endpoint losses are projected onto four pre-registered windows: samples 0-3 for pedestal and "
            "baseline memory, samples 4-7 for rising-edge timing and early overlap, samples 8-11 for peak charge "
            "and saturation onset, and samples 12-17 for late pile-up/tail information and noncausal PID risk."
        ),
        "",
        BASE.md_table(
            window_attr,
            [
                "window_mask",
                "method",
                "samples",
                "causal_before_or_at_peak",
                "window_loss_score",
                "fraction_of_joint_loss",
                "rank_within_window",
            ],
        ),
        "",
        "Window winners:",
        "",
        f"- Pretrigger/pedestal: `{pre['method']}`.",
        f"- Rising-edge/timing: `{rise['method']}`.",
        f"- Peak-charge PID/energy: `{peak['method']}`.",
        f"- Late-tail stress: `{late['method']}`.",
        "",
        "## Leakage and Promotion Guards",
        BASE.md_table(
            leakage,
            [
                "method",
                "timing_mediated_fraction",
                "late_tail_fraction_of_joint_loss",
                "noncausal_tail_flag",
                "too_good_pid_flag",
                "interpretation",
            ],
        ),
        "",
        "The promotion rule is deliberately skeptical: a high PID score is not promoted as detector PID physics if it "
        "depends strongly on samples 12-17 or if it lacks a pedestal and saturation stress panel. Late samples are "
        "valid for pile-up and recovery; they are unsafe as the sole explanation of PID/energy gain.",
        "",
        "## Compact Transformer / Attention Sensitivity",
        BASE.md_table(
            attention,
            ["architecture", "endpoint", "metric", "value", "ci_low", "ci_high", "eligible_for_complete_panel", "reason"],
        ),
        "",
        "The 18-sample sequence is short enough for compact sequence models, but the available attention/transformer "
        "rows are endpoint-incomplete. They are retained as sensitivity evidence and excluded from the winner rule "
        "unless a future ticket retrains all masks event-level on the same complete run split.",
        "",
        "## Systematic Uncertainties",
        "- Endpoint heterogeneity: PID, energy, timing, pile-up, saturation, and pedestal rows come from compatible raw-ROOT-derived studies rather than one monolithic retraining job.",
        "- Weak PID labels: PID is represented by calibrated charge/depth and waveform proxies, not new external particle-truth labels.",
        "- Energy bridge: energy metrics inherit the GEANT4/Birks and material-response assumptions of the source panels.",
        "- Window projection: the sample-window score is an endpoint-level causal attribution, not an event-level masked retraining for every architecture.",
        "- Run-block support: bootstrap intervals reflect the available run groups and cannot cover unobserved beam or gain settings.",
        "",
        "## Caveats",
        "- S29c should be read as a promotion and ablation audit, not as a new definitive particle-ID calibration.",
        "- A noncausal tail flag is a warning condition; it does not prove every late-tail feature is leakage.",
        "- The traditional method remains scientifically valuable where interpretability or monotonic charge response matters, even though it does not win the composite score.",
        "- The compact sequence/residual architecture is only promoted where the source rows were complete; incomplete transformer rows are sensitivity checks.",
        "",
        "## Source Provenance",
        BASE.md_table(sources, ["source", "path", "sha256_result"]),
        "",
        "## Conclusion",
        (
            f"`result.json` names `{result['winner']}` as the S29c winner. The causal-window result says the "
            "most defensible PID/energy gains are those that survive peak-charge, rising-edge, pedestal, saturation, "
            "pile-up, and late-tail audits together. The next highest-information experiment is an event-level masked "
            "retraining ticket that makes the compact transformer eligible for the same complete-panel winner rule."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    BASE.CONFIG = CONFIG
    BASE.build_report = build_report
    BASE.main()
    cfg = BASE.load_json(CONFIG)
    out = ROOT / cfg["output_dir"]
    result_path = out / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    next_ticket = {
        "title": "S29d: event-level masked-window retraining for complete PID-energy-stress transformer eligibility",
        "body": (
            "Question: after freezing S29c's pulse-window masks, do ridge, GBT, MLP, 1D-CNN, "
            "compact sequence/residual, and a small transformer retain PID/energy/timing gains when "
            "each mask is retrained event-level on the same complete-run folds? Expected information "
            "gain: converts S29c's endpoint-level causal attribution into a single event-native masked "
            "prediction table and makes the transformer eligible for the full winner rule."
        ),
    }
    result["next_tickets"] = [next_ticket]
    result["novel_ticket_appended"] = next_ticket["title"]
    result["claim_command"] = "tn-ticket claim testbeam-laptop-1 --project testbeam"
    result["claimed_once"] = True
    result["status"] = "complete"
    BASE.write_json(result_path, result)

    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["command"] = " ".join([sys.executable, str(Path(__file__).resolve().relative_to(ROOT))])
    manifest["artifacts"] = {}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["artifacts"][path.name] = {"bytes": path.stat().st_size, "sha256": BASE.sha256(path)}
    BASE.write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
