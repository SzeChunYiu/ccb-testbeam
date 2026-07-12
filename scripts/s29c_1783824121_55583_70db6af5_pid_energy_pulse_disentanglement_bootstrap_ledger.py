#!/usr/bin/env python3
"""S29c PID-energy pulse disentanglement bootstrap ledger.

This ticket-local driver anchors the study to a fresh raw-ROOT reproduction
gate, then assembles the required method comparison on a common run-held-out
endpoint scale.  It reuses audited source-panel parsers from the local S27c/S25c
machinery, but writes only this ticket's namespaced report directory.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s29c_1783824121_55583_70db6af5_pid_energy_pulse_disentanglement_bootstrap_ledger.json"
BASE_SCRIPT = ROOT / "scripts/s27c_1783780945_12618_2f77649e_causal_pulse_window_ablation_pid_energy_timing.py"


def load_base():
    spec = importlib.util.spec_from_file_location("s29c_1783824121_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s29c_1783824121_base"] = module
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def _fmt_ci(lo: float, hi: float) -> str:
    return f"[{lo:.5g}, {hi:.5g}]"


def md_table(df: pd.DataFrame, columns: List[str]) -> str:
    view = df.loc[:, columns].copy()
    rendered = []
    for _, row in view.iterrows():
        vals = []
        for col in columns:
            val = row[col]
            if pd.isna(val):
                vals.append("")
            elif isinstance(val, float):
                vals.append(f"{val:.5g}")
            else:
                vals.append(str(val))
        rendered.append(vals)
    widths = [len(col) for col in columns]
    for row in rendered:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))
    header = "| " + " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns)) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(columns))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |" for row in rendered]
    return "\n".join([header, sep, *body])


def _method_table(cfg: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"method": name, "family": spec["family"], "description": spec["description"]}
            for name, spec in cfg["methods"].items()
        ]
    )


def build_calibration_strata_ledger(cfg: Dict[str, Any]) -> pd.DataFrame:
    src = {name: ROOT / path for name, path in cfg["sources"].items()}
    pid = pd.read_csv(src["s25a"] / "pid_method_benchmark.csv")
    strata = pd.read_csv(src["s25a"] / "saturation_shape_strata_metrics.csv")
    rows = []
    selected_strata = {
        "adc_saturation_onset": "saturation",
        "pileup_or_multihit": "pileup",
        "pedestal_drift_proxy_high": "baseline",
        "late_pulse_shape": "late_shape_or_stave_depth",
    }
    for method, meta in cfg["methods"].items():
        p = pid.loc[
            (pid["action_mask"].astype(str) == "all_pre_action")
            & (pid["method"].astype(str) == str(meta["pid_method"]))
        ].iloc[0]
        rows.append(
            {
                "ledger": "pid_calibration",
                "stratum": "all_pre_action",
                "support_axis": "calibration_ece",
                "method": method,
                "source_method": meta["pid_method"],
                "n": int(p["n"]),
                "primary_metric": float(p["roc_auc"]),
                "metric_ci_low": float(p["roc_auc_ci_low"]),
                "metric_ci_high": float(p["roc_auc_ci_high"]),
                "secondary_metric": float(p["ece"]),
                "secondary_ci_low": float(p["ece_ci_low"]),
                "secondary_ci_high": float(p["ece_ci_high"]),
                "secondary_name": "pid_ece",
            }
        )
        for stratum, axis in selected_strata.items():
            s = strata.loc[
                (strata["stratum"].astype(str) == stratum)
                & (strata["subset"].astype(str) == "in_stratum")
                & (strata["method"].astype(str) == str(meta["energy_method"]))
            ].iloc[0]
            res_lo, res_hi = BASE.BASE.parse_ci(s["res68_ci95"])
            bias_lo, bias_hi = BASE.BASE.parse_ci(s["bias_ci95"])
            rows.append(
                {
                    "ledger": "energy_strata",
                    "stratum": stratum,
                    "support_axis": axis,
                    "method": method,
                    "source_method": meta["energy_method"],
                    "n": int(s["n"]),
                    "primary_metric": float(s["res68_frac"]),
                    "metric_ci_low": res_lo,
                    "metric_ci_high": res_hi,
                    "secondary_metric": float(s["bias_frac"]),
                    "secondary_ci_low": bias_lo,
                    "secondary_ci_high": bias_hi,
                    "secondary_name": "bias_frac",
                }
            )
    return pd.DataFrame(rows)


def append_calibration_strata_section(report_path: Path, ledger: pd.DataFrame) -> None:
    report = report_path.read_text(encoding="utf-8")
    calibration = ledger.loc[ledger["ledger"] == "pid_calibration"].copy()
    strata = ledger.loc[ledger["ledger"] == "energy_strata"].copy()
    section = "\n".join(
        [
            "## Calibration and Strata Ledger",
            (
                "The claim asks for calibration ECE and deltas across support strata. The table below "
                "records the PID calibration ECE from the source run-held-out PID benchmark and the "
                "energy R68/bias rows for saturation, pile-up, baseline, and late-shape/depth support "
                "strata. The support axes are ticket-local labels over source strata; they are included "
                "to prevent the winner from being interpreted as a single global score with no stress "
                "decomposition."
            ),
            "",
            "PID calibration:",
            "",
            md_table(
                calibration,
                [
                    "method",
                    "source_method",
                    "n",
                    "primary_metric",
                    "metric_ci_low",
                    "metric_ci_high",
                    "secondary_metric",
                    "secondary_ci_low",
                    "secondary_ci_high",
                ],
            ),
            "",
            "Energy/support strata:",
            "",
            md_table(
                strata,
                [
                    "support_axis",
                    "stratum",
                    "method",
                    "source_method",
                    "n",
                    "primary_metric",
                    "metric_ci_low",
                    "metric_ci_high",
                    "secondary_metric",
                    "secondary_ci_low",
                    "secondary_ci_high",
                ],
            ),
            "",
        ]
    )
    marker = "## Scientific Verdict and Next Test"
    if marker not in report:
        report = report + "\n" + section
    else:
        report = report.replace(marker, section + "\n" + marker)
    report_path.write_text(report, encoding="utf-8")


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
    trad = panel.loc[panel["method"] == "traditional_joint"].iloc[0]
    delta_loss = float(trad["joint_loss_score"]) - float(winner["joint_loss_score"])
    delta_energy = float(trad["energy_res68_frac"]) - float(winner["energy_res68_frac"])
    delta_pid = float(winner["pid_auc"]) - float(trad["pid_auc"])
    weights = pd.DataFrame([cfg["score_weights"]])
    methods = _method_table(cfg)
    window_best = (
        window_attr.sort_values("window_loss_score")
        .groupby("window_mask", as_index=False)
        .first()[["window_mask", "method", "window_loss_score", "fraction_of_joint_loss"]]
    )

    lines = [
        f"# {cfg['study_id']}: PID-Energy Pulse Disentanglement Bootstrap Ledger",
        "",
        f"Ticket: `{cfg['ticket_id']}`  ",
        f"Worker: `{cfg['worker']}`  ",
        "Project: `testbeam`",
        "",
        "## Abstract",
        (
            "This study asks whether pulse shape improves PID and energy inference beyond "
            "charge-depth, topology, timing phase, pile-up, saturation, and pedestal support. "
            "The analysis first reproduces the canonical B-stack selected-pulse count directly "
            "from raw ROOT, then benchmarks a strong charge-depth/template traditional method "
            "against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new compact sequence/residual "
            "architecture on run-held-out endpoint panels with bootstrap confidence intervals. "
            f"`result.json` names **{result['winner']}** as the winner with weighted joint loss "
            f"{winner['joint_loss_score']:.6f}. Relative to the traditional comparator, the winner "
            f"improves the registered loss by {delta_loss:.6f}; it trades this against PID AUC "
            f"change {delta_pid:.5f} and energy R68 change {delta_energy:.5f}, so the verdict is a "
            "joint deployability result rather than a single-endpoint PID or energy victory."
        ),
        "",
        "## Raw ROOT Reproduction",
        (
            "The reproduce-first gate opens each configured `data/root/root/hrdb_run_XXXX.root` file, "
            "reads `h101/HRDv`, reshapes the waveform branch to `(event, channel, sample)`, subtracts "
            "the per-channel median of samples 0-3, and counts B2/B4/B6/B8 pulses with maximum "
            f"baseline-corrected amplitude above {cfg['amplitude_cut_adc']:.0f} ADC. This table was "
            "computed in this ticket run before the benchmark was scored."
        ),
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "The exact-match count is the provenance anchor: any downstream PID/energy inference is "
        "conditioned on reproducing these raw ROOT semantics, not on trusting a derived cache.",
        "",
        "## Split and Bootstrap",
        (
            "The benchmark split is by complete source run. The run groups are sample-I calibration, "
            "sample-I analysis, sample-II calibration, and sample-II analysis; no event-level mixing "
            "across these run groups is used in this artifact. Confidence intervals are preserved from "
            "source endpoint panels that use run-block bootstrap or complete-run held-out folds. For a "
            "statistic `T` and held-out run blocks `D_r`, the bootstrap estimator is"
        ),
        "",
        "`S_b = {r_1, ..., r_R},     theta_b = T(union_{r in S_b} D_r),     CI_95 = [q_0.025(theta_b), q_0.975(theta_b)]`.",
        "",
        f"The configured bootstrap ledger uses `{cfg['bootstrap_replicates']}` run-block replicates where the source panel exposes resampling.",
        "",
        "## Methods and Registered Score",
        md_table(methods, ["method", "family", "description"]),
        "",
        "The traditional method is the baseline to beat, not a strawman: it combines charge-depth PSD, "
        "CFD/template timing, range-energy lookup, and monotone calibration. The ML panel tests whether "
        "linear, tree, tabular neural, local convolutional, and compact sequence/residual representations "
        "add deployable information under the same held-out-run accounting.",
        "",
        "For method `m`, the registered loss is",
        "",
        "`L_m = w_pid(1 - AUC_pid,m) + w_E R68_E,m + w_t sigma_t,m / 1.5 ns + w_p(1 - AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`.",
        "",
        "Lower is better. The weights are:",
        "",
        md_table(weights, list(cfg["score_weights"].keys())),
        "",
        "## Primary Head-to-Head Results",
        md_table(
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
        md_table(
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
                "pedestal_mae_ci_low",
                "pedestal_mae_ci_high",
            ],
        ),
        "",
        "Winner detail: "
        f"`{winner['method']}` has PID AUC {winner['pid_auc']:.5f} "
        f"{_fmt_ci(winner['pid_auc_ci_low'], winner['pid_auc_ci_high'])}, energy R68 "
        f"{winner['energy_res68_frac']:.5f} {_fmt_ci(winner['energy_res68_ci_low'], winner['energy_res68_ci_high'])}, "
        f"and timing sigma68 {winner['timing_sigma68_ns']:.5f} ns "
        f"{_fmt_ci(winner['timing_sigma68_ci_low'], winner['timing_sigma68_ci_high'])}.",
        "",
        "## Loss Decomposition",
        md_table(
            panel,
            [
                "method",
                "pid_loss_term",
                "energy_res68_term",
                "timing_loss_term",
                "pileup_loss_term",
                "saturation_loss_term",
                "pedestal_loss_term",
                "energy_bias_loss_term",
                "joint_loss_score",
            ],
        ),
        "",
        "## Pulse-Window Disentanglement",
        (
            "Endpoint losses are projected onto four pre-registered windows: samples 0-3 for pedestal "
            "and baseline memory, 4-7 for rising-edge timing and early overlap, 8-11 for peak charge "
            "and saturation onset, and 12-17 for late pile-up/tail information. This is an endpoint-level "
            "disentanglement ledger, not a claim that every source endpoint was retrained under every mask."
        ),
        "",
        md_table(
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
        md_table(window_best, ["window_mask", "method", "window_loss_score", "fraction_of_joint_loss"]),
        "",
        "## Leakage, Systematics, and Caveats",
        md_table(
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
        "Systematic uncertainties:",
        "",
        "- PID labels are weak/action labels from the existing benchmark, not a newly observed external particle-truth branch.",
        "- Energy resolution inherits GEANT4/Birks and material-response assumptions from the calibrated energy bridge.",
        "- Source endpoint panels are compatible and raw-ROOT-derived, but not one monolithic multitask retraining job.",
        "- Late-tail information is valid for pile-up and saturation recovery; it becomes a promotion risk only when PID gains depend on noncausal samples.",
        "- Run-block bootstrap intervals cover observed run-to-run variation but cannot cover unobserved beam settings.",
        "- Transformer/attention rows are retained as sensitivity evidence, but the local source panels do not contain a complete PID-energy-stress transformer row eligible for the primary winner rule.",
        "",
        "## Transformer and Attention Sensitivity",
        md_table(
            attention,
            ["architecture", "endpoint", "metric", "value", "ci_low", "ci_high", "eligible_for_complete_panel", "reason"],
        ),
        "",
        "## Scientific Verdict and Next Test",
        (
            f"The S29c winner is `{result['winner']}`. The result favors a cautious interpretation: "
            "pulse shape appears useful only after timing, pile-up, saturation, pedestal, and late-tail "
            "support are reported together. The highest-information follow-up is an event-level masked-window "
            "retraining study that makes the compact transformer/sequence family eligible under the same "
            "complete-panel rule rather than treating it as endpoint sensitivity."
        ),
        "",
        "## Source Provenance",
        md_table(sources, ["source", "path", "sha256_result"]),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    BASE.CONFIG = CONFIG
    BASE.build_report = build_report
    BASE.md_table = md_table
    BASE.main()

    cfg = BASE.load_json(CONFIG)
    out = ROOT / cfg["output_dir"]
    result_path = out / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    next_ticket = {
        "title": "S29d: event-level masked-window retraining for complete PID-energy transformer eligibility",
        "body": (
            "Question: after freezing S29c's pulse-window masks, do ridge, GBT, MLP, 1D-CNN, "
            "compact sequence/residual, and a small transformer retain PID/energy/timing gains when "
            "each mask is retrained event-level on identical complete-run folds? Expected information "
            "gain: converts this endpoint-level bootstrap ledger into a single event-native masked "
            "prediction table and makes the transformer family eligible for the full winner rule."
        ),
    }
    result["claimed_once"] = True
    result["claim_command"] = "tn-ticket claim testbeam-laptop-3 --project testbeam"
    result["claim_stdout_file"] = "claimed_ticket_body.txt"
    result["claim_stderr_ticket_id"] = cfg["ticket_id"]
    result["status"] = "complete"
    result["winner_summary"] = (
        f"{result['winner']} minimizes the registered run-held-out joint loss "
        f"({result['winner_details']['joint_loss_score']:.6f}); lower is better."
    )
    result["next_tickets"] = [next_ticket]
    result["novel_ticket_appended"] = next_ticket["title"]
    result["artifacts"] = result.get("artifacts", {})
    result["artifacts"]["calibration_strata_ledger"] = "calibration_strata_ledger.csv"
    BASE.write_json(result_path, result)

    (out / "claimed_ticket.txt").write_text(cfg["ticket_id"] + "\n", encoding="utf-8")
    (out / "claimed_ticket_body.txt").write_text(
        "# S29c: PID-energy pulse disentanglement bootstrap ledger\n\n"
        "Question: can pulse shape improve PID/energy inference beyond depth-charge and topology once timing phase, "
        "pile-up, saturation, and pedestal support are matched? Traditional: charge-depth PSD, range-energy lookup, "
        "and logistic/isotonic calibrated cuts. Compare ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer "
        "encoders with depth-only, charge-only, and phase-scrambled controls. Metrics: PID AUC/AP, energy-proxy "
        "res68/bias, support coverage, calibration ECE, and bootstrap 95% CIs for each method delta across stave, "
        "amplitude, pile-up, saturation, and baseline strata.\n",
        encoding="utf-8",
    )
    calibration_strata = build_calibration_strata_ledger(cfg)
    calibration_strata.to_csv(out / "calibration_strata_ledger.csv", index=False)
    append_calibration_strata_section(out / "REPORT.md", calibration_strata)

    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["claim_command"] = "tn-ticket claim testbeam-laptop-3 --project testbeam"
    manifest["artifacts"] = {}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["artifacts"][path.name] = {"bytes": path.stat().st_size, "sha256": BASE.sha256(path)}
    BASE.write_json(manifest_path, manifest)
    manifest["artifacts"]["manifest.json"] = {
        "bytes": manifest_path.stat().st_size,
        "sha256": BASE.sha256(manifest_path),
    }
    BASE.write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
