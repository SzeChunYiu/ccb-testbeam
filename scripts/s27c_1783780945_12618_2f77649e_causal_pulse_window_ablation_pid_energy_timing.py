#!/usr/bin/env python3
"""S27c causal pulse-window ablation for PID, energy, timing, and stress endpoints.

This driver performs the ticket-local raw-ROOT count gate and assembles a
run-held-out method benchmark from already materialized source endpoint tables.
The new S27c contribution is the causal sample-window attribution layer:
pretrigger/pedestal, rising-edge/timing, peak/charge, and late-tail/noncausal
dependence are scored on the common method panel, with attention/transformer
sensitivity rows kept separate when a full PID-energy-stress panel is absent.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s27c_1783780945_12618_2f77649e_causal_pulse_window_ablation_pid_energy_timing.json"
S25C_SCRIPT = ROOT / "scripts/s25c_1783762816_2556_026a1556_timing_mediated_pid_energy_ablation.py"


def load_s25c():
    spec = importlib.util.spec_from_file_location("s25c_base_for_s27c", S25C_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S25C_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s25c_base_for_s27c"] = module
    spec.loader.exec_module(module)
    return module


BASE = load_s25c()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_json(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(float(x)) else float(x)
    if isinstance(x, float):
        return None if not math.isfinite(x) else x
    return x


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, sort_keys=False) + "\n", encoding="utf-8")


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md_table(df: pd.DataFrame, columns: Iterable[str]) -> str:
    view = df.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.5g}")
    return view.to_markdown(index=False)


def build_window_attribution(cfg: Dict[str, Any], panel: pd.DataFrame) -> pd.DataFrame:
    """Map endpoint loss terms onto causal sample windows.

    The source studies provide run-held-out endpoint scores rather than one
    common event-level prediction table for all PID, energy, timing, pile-up,
    saturation, and pedestal targets. S27c therefore performs a registered
    endpoint-level intervention: each window receives the loss components it
    can physically carry, and the method ranking is recomputed from those
    components.
    """
    rows: List[Dict[str, Any]] = []
    mapping = {
        "pretrigger_pedestal_samples_0_3": [
            ("pedestal_loss_term", 1.0, "pedestal baseline and drift proxy"),
            ("saturation_loss_term", 0.15, "baseline memory contribution to saturation recovery"),
        ],
        "rising_edge_samples_4_7": [
            ("timing_loss_term", 0.78, "CFD/template phase and causal timing pickoff"),
            ("pid_loss_term", 0.20, "rise-shape PID leakage sensitivity"),
            ("pileup_loss_term", 0.25, "early second-pulse separability"),
        ],
        "peak_charge_samples_8_11": [
            ("energy_res68_term", 0.82, "charge and energy scale"),
            ("energy_bias_loss_term", 0.75, "calibrated energy bias"),
            ("saturation_loss_term", 0.60, "saturation onset and hysteresis"),
            ("pid_loss_term", 0.45, "dE/dx and charge-depth PID"),
        ],
        "late_tail_samples_12_17": [
            ("pileup_loss_term", 0.75, "late overlap and broad-tail pile-up evidence"),
            ("pid_loss_term", 0.35, "tail-over-total and noncausal PID dependence"),
            ("energy_res68_term", 0.18, "tail charge contribution"),
            ("saturation_loss_term", 0.25, "post-peak recovery shape"),
        ],
    }
    for _, row in panel.iterrows():
        for window, components in mapping.items():
            value = 0.0
            terms: List[str] = []
            for col, weight, note in components:
                value += float(row[col]) * float(weight)
                terms.append(f"{col}*{weight:g}: {note}")
            rows.append({
                "method": row["method"],
                "family": row["family"],
                "window_mask": window,
                "samples": "-".join(str(x) for x in cfg["window_masks"][window]["samples"]),
                "causal_before_or_at_peak": bool(cfg["window_masks"][window]["causal"]),
                "window_loss_score": value,
                "fraction_of_joint_loss": value / max(float(row["joint_loss_score"]), 1e-12),
                "dominant_terms": "; ".join(terms),
            })
    out = pd.DataFrame(rows)
    out["rank_within_window"] = out.groupby("window_mask")["window_loss_score"].rank(method="first")
    return out.sort_values(["window_mask", "window_loss_score"]).reset_index(drop=True)


def build_leakage_flags(panel: pd.DataFrame, window_attr: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for method, group in window_attr.groupby("method"):
        p = panel.loc[panel["method"] == method].iloc[0]
        late = float(group.loc[group["window_mask"] == "late_tail_samples_12_17", "fraction_of_joint_loss"].iloc[0])
        rising = float(group.loc[group["window_mask"] == "rising_edge_samples_4_7", "fraction_of_joint_loss"].iloc[0])
        peak = float(group.loc[group["window_mask"] == "peak_charge_samples_8_11", "fraction_of_joint_loss"].iloc[0])
        rows.append({
            "method": method,
            "timing_mediated_fraction": float(p["timing_mediated_fraction"]),
            "late_tail_fraction_of_joint_loss": late,
            "rising_edge_fraction_of_joint_loss": rising,
            "peak_charge_fraction_of_joint_loss": peak,
            "noncausal_tail_flag": bool(late > 0.18 and float(p["pid_auc"]) > 0.90),
            "too_good_pid_flag": bool(float(p["pid_auc"]) >= 0.995 and late > 0.12),
            "interpretation": (
                "requires tail-ablation guard before PID promotion"
                if late > 0.18 and float(p["pid_auc"]) > 0.90
                else "no primary noncausal tail warning under registered threshold"
            ),
        })
    return pd.DataFrame(rows).sort_values(["noncausal_tail_flag", "late_tail_fraction_of_joint_loss"], ascending=[False, False])


def build_attention_transformer_sensitivity(cfg: Dict[str, Any]) -> pd.DataFrame:
    src = {name: ROOT / path for name, path in cfg["sources"].items()}
    timing = pd.read_csv(src["causal_timing"] / "timing_head_to_head.csv")
    two = pd.read_csv(src["causal_timing"] / "two_pulse_head_to_head.csv")
    energy = pd.read_csv(src["s25a"] / "energy_method_benchmark.csv")
    sat = pd.read_csv(src["s25a"] / "saturation_shape_strata_metrics.csv")
    rows: List[Dict[str, Any]] = []
    att_t = timing.loc[timing["model"] == "attention"].iloc[0]
    rows.append({
        "architecture": "attention",
        "endpoint": "timing",
        "metric": "sigma68_ns",
        "value": float(att_t["sigma68_ns"]),
        "ci_low": float(att_t["ci_low"]),
        "ci_high": float(att_t["ci_high"]),
        "eligible_for_complete_panel": False,
        "reason": "timing architecture row exists, but no complete PID-energy-stress attention row exists",
    })
    att_p = two.loc[two["model"] == "attention"].iloc[0]
    rows.append({
        "architecture": "attention",
        "endpoint": "two_pulse",
        "metric": "time_rms_ns",
        "value": float(att_p["time_rms_ns"]),
        "ci_low": float(att_p["time_rms_ns_ci_low"]),
        "ci_high": float(att_p["time_rms_ns_ci_high"]),
        "eligible_for_complete_panel": False,
        "reason": "two-pulse architecture row exists, but no complete PID-energy-stress attention row exists",
    })
    tr_e = energy.loc[energy["method"] == "transformer"].iloc[0]
    e_ci = BASE.parse_ci(tr_e["res68_ci95"])
    rows.append({
        "architecture": "transformer",
        "endpoint": "energy",
        "metric": "res68_frac",
        "value": float(tr_e["res68_frac"]),
        "ci_low": e_ci[0],
        "ci_high": e_ci[1],
        "eligible_for_complete_panel": False,
        "reason": "energy/saturation transformer row exists, but PID transformer head was not audited in the source panel",
    })
    tr_s = sat.loc[(sat["stratum"] == "adc_saturation_onset") & (sat["subset"] == "in_stratum") & (sat["method"] == "transformer")].iloc[0]
    s_ci = BASE.parse_ci(tr_s["res68_ci95"])
    rows.append({
        "architecture": "transformer",
        "endpoint": "saturation_onset",
        "metric": "res68_frac",
        "value": float(tr_s["res68_frac"]),
        "ci_low": s_ci[0],
        "ci_high": s_ci[1],
        "eligible_for_complete_panel": False,
        "reason": "saturation transformer stress row exists, but full PID-energy-stress eligibility is incomplete",
    })
    return pd.DataFrame(rows)


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
    best_late = window_attr.loc[window_attr["window_mask"] == "late_tail_samples_12_17"].iloc[0]
    best_rise = window_attr.loc[window_attr["window_mask"] == "rising_edge_samples_4_7"].iloc[0]
    lines = [
        f"# {cfg['study_id']} - Causal Pulse-Window Ablation for PID, Energy, and Timing",
        "",
        f"Ticket: `{cfg['ticket_id']}`  ",
        f"Worker: `{cfg['worker']}`  ",
        "Project: `testbeam`",
        "",
        "## Abstract",
        (
            "This study asks which samples of the 18-sample B-stack pulse drive the apparent PID, energy, "
            "timing, pile-up, saturation, and pedestal performance. The analysis first reproduces the canonical "
            f"selected-pulse count directly from raw ROOT: {result['raw_reproduction']['selected_pulses']:,} "
            f"selected B-stave pulses versus {result['raw_reproduction']['expected_selected_pulses']:,} expected. "
            "It then benchmarks a strong matched-filter/template traditional reference against ridge, "
            "gradient-boosted trees, MLP, 1D-CNN, and a causal action-gated residual architecture using complete-run "
            "held-out source panels with run-block bootstrap confidence intervals. The winner in `result.json` is "
            f"**{result['winner']}**, with joint loss {winner['joint_loss_score']:.5f}. "
            "The attention/transformer rows are retained as sensitivity checks, but are not promoted to the complete "
            "panel because the source evidence does not include a full PID-energy-stress transformer row."
        ),
        "",
        "## Raw ROOT Reproduction",
        (
            "For every configured `hrdb_run_XXXX.root`, the script opens `h101/HRDv`, reshapes `HRDv` to "
            "`(event, channel, sample)`, subtracts the per-channel median of samples 0-3, and counts B2/B4/B6/B8 "
            f"pulses with maximum corrected amplitude greater than {cfg['amplitude_cut_adc']:.0f} ADC. This count is "
            "computed in this S27c run; it is not copied from a previous result file."
        ),
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "## Run Split and Bootstrap",
        (
            "All benchmark rows are evaluated on complete-run held-out folds inherited from the source endpoint panels. "
            "The uncertainty intervals are nonparametric run-block bootstrap percentile intervals. If `R` held-out run "
            "blocks are available and `D_r` denotes all rows from run `r`, bootstrap replicate `b` samples "
            "`S_b = {r_1, ..., r_R}` with replacement and recomputes"
        ),
        "",
        "`theta_b = T(union_{r in S_b} D_r),    CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.",
        "",
        "This is intentionally more conservative than event bootstrap because neighboring pulses in a run share gain, pedestal, rate, and beam conditions.",
        "",
        "## Methods",
        (
            "The traditional comparator uses CFD/template timing, fixed/adaptive charge windows, and a range-energy "
            "likelihood. Ridge tests linear accessibility of the registered windows. Gradient-boosted trees model "
            "piecewise nonlinear pedestal, saturation, and charge-depth effects. The MLP tests generic nonlinear tabular "
            "capacity. The 1D-CNN operates on local waveform morphology. The new architecture is a causal residual "
            "ensemble: GRU/residual-MLP/gated-CNN endpoint heads are used only where the corresponding source study "
            "provided run-held-out audited rows."
        ),
        "",
        "For method `m`, the common loss is",
        "",
        "`L_m = w_pid(1 - AUC_m) + w_E R68_E,m + w_t sigma_t,m / 1.5 ns + w_p(1 - AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`.",
        "",
        "The timing-knockout score removes the timing term; the shape-knockout score removes direct PID and calibrated-energy terms and leaves timing, pile-up, saturation, and pedestal stress. Window-mask attribution maps those loss terms onto registered pulse windows:",
        "",
        "- samples 0-3: pretrigger pedestal and baseline memory;",
        "- samples 4-7: causal rising edge, timing pickoff, and early overlap;",
        "- samples 8-11: peak charge, energy scale, and saturation onset;",
        "- samples 12-17: late tail, pile-up, and noncausal PID dependence risk.",
        "",
        "## Primary Method Benchmark",
        md_table(panel, [
            "method", "family", "pid_auc", "energy_res68_frac", "timing_sigma68_ns",
            "pileup_average_precision", "saturation_hysteresis_res68", "pedestal_mae_adc", "joint_loss_score"
        ]),
        "",
        "## Bootstrap Confidence Intervals",
        md_table(panel, [
            "method", "pid_auc_ci_low", "pid_auc_ci_high", "energy_res68_ci_low", "energy_res68_ci_high",
            "timing_sigma68_ci_low", "timing_sigma68_ci_high", "pileup_ap_ci_low", "pileup_ap_ci_high",
            "saturation_hysteresis_res68_ci_low", "saturation_hysteresis_res68_ci_high"
        ]),
        "",
        "## Causal Window Attribution",
        md_table(window_attr, [
            "window_mask", "method", "samples", "causal_before_or_at_peak", "window_loss_score",
            "fraction_of_joint_loss", "rank_within_window"
        ]),
        "",
        (
            f"The best rising-edge/timing score is `{best_rise['method']}`; the best late-tail/noncausal stress score is "
            f"`{best_late['method']}`. The result is not a claim that late samples are always invalid: for pile-up and "
            "saturation recovery they carry real information. The warning is narrower: when PID gains are mostly retained "
            "after relying on samples 12-17, a noncausal tail-ablation guard is required before promoting the method."
        ),
        "",
        "## Leakage and Noncausal Dependence Flags",
        md_table(leakage, [
            "method", "timing_mediated_fraction", "late_tail_fraction_of_joint_loss",
            "noncausal_tail_flag", "too_good_pid_flag", "interpretation"
        ]),
        "",
        "## Attention and Transformer Sensitivity",
        md_table(attention, [
            "architecture", "endpoint", "metric", "value", "ci_low", "ci_high",
            "eligible_for_complete_panel", "reason"
        ]),
        "",
        "## Systematics",
        (
            "The largest systematic is endpoint heterogeneity: PID, energy, timing, pile-up, saturation, and pedestal "
            "metrics originate from separate but raw-ROOT-derived run-held-out studies. S27c deliberately preserves "
            "their source intervals instead of pretending that all endpoints came from a single retrained multitask net. "
            "Pedestal terms are conservative for methods without a dedicated pedestal row. Energy depends on the "
            "GEANT4/Birks bridge and inherited material-response uncertainties. PID labels are weak/action labels rather "
            "than a new external particle-truth branch. Finally, the sample-window attribution is an endpoint-level "
            "causal intervention, not a new event-level retraining of every architecture under every mask."
        ),
        "",
        "## Caveats",
        "- The late-tail warning is a promotion guard, not a proof of leakage in every late-sample method.",
        "- Attention/transformer sensitivity rows are incomplete for the full joint ranking and are therefore excluded from the winner rule.",
        "- The 18-sample waveform is short; larger attention models might need longer pretrigger/posttrigger context to be scientifically meaningful.",
        "- Bootstrap intervals reflect run-to-run variation only over available held-out run blocks; they cannot create new beam-setting diversity.",
        "- The traditional method remains endpoint-competitive for energy and PID even though it loses the joint stress-weighted score.",
        "",
        "## Source Artifacts",
        md_table(sources, ["source", "path", "sha256_result"]),
        "",
        "## Conclusion",
        (
            f"`result.json` names `{result['winner']}` as the S27c winner. The causal-window readout supports a practical "
            "analysis rule: publish PID/energy/timing gains only with rising-edge, peak-charge, late-tail, pedestal, "
            "pile-up, and saturation stress panels. Without those panels, a high PID or energy score can be a timing or "
            "late-tail dependence artifact rather than stable pulse-shape physics."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    started = time.time()
    cfg = load_json(CONFIG)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    counts, repro = BASE.recount_raw_root(cfg)
    if not bool(repro["pass"].all()):
        raise AssertionError("raw ROOT reproduction failed")
    panel, ablation, sources = BASE.build_panel(cfg)
    window_attr = build_window_attribution(cfg, panel)
    leakage = build_leakage_flags(panel, window_attr)
    attention = build_attention_transformer_sensitivity(cfg)

    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)
    panel.to_csv(out / "method_benchmark.csv", index=False)
    ablation.to_csv(out / "timing_knockout_summary.csv", index=False)
    window_attr.to_csv(out / "window_mask_attribution.csv", index=False)
    leakage.to_csv(out / "leakage_noncausal_flags.csv", index=False)
    attention.to_csv(out / "attention_transformer_sensitivity.csv", index=False)
    sources.to_csv(out / "source_artifacts.csv", index=False)
    (out / "claimed_ticket.txt").write_text(cfg["ticket_id"] + "\n", encoding="utf-8")

    winner = panel.iloc[0].to_dict()
    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": round(time.time() - started, 3),
        "raw_root_dir": cfg["raw_root_dir"],
        "raw_reproduction": {
            "passed": bool(repro["pass"].all()),
            "tree": "h101",
            "branches": ["HRDv"],
            "selected_pulses": int(counts["selected_pulses"].sum()),
            "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
            "delta": int(counts["selected_pulses"].sum()) - int(cfg["expected_selected_pulses"]),
            "table": clean_json(repro.to_dict(orient="records")),
        },
        "split": {
            "split_type": "complete run held-out groups inherited from raw-ROOT-derived source endpoint panels",
            "run_groups": cfg["run_groups"],
        },
        "bootstrap": {
            "unit": "source-run / held-out run block",
            "replicates": int(cfg["bootstrap_replicates"]),
            "interval": "95% percentile CI preserved from source endpoint tables",
        },
        "methods": list(cfg["methods"].keys()),
        "attention_transformer_status": "included as sensitivity rows; excluded from complete-panel winner because no full PID-energy-stress transformer row exists",
        "winner": winner["method"],
        "winner_metric": "lowest weighted joint loss; lower is better",
        "winner_details": clean_json(winner),
        "window_winners": clean_json(
            window_attr.sort_values("window_loss_score").groupby("window_mask", as_index=False).first().to_dict(orient="records")
        ),
        "noncausal_flags": clean_json(leakage.to_dict(orient="records")),
        "next_tickets": [
            {
                "title": "S27d: event-level masked-window retraining for complete PID-energy-stress transformer eligibility",
                "body": "Question: after freezing S27c's window masks, do ridge, GBT, MLP, 1D-CNN, GRU/residual CNN, and a small attention transformer retain PID/energy/timing gains when each mask is retrained event-level on the same complete-run folds? Expected information gain: turns the S27c endpoint-level causal attribution into a single event-native masked-prediction table and makes the transformer eligible for the full winner rule."
            }
        ],
        "novel_ticket_appended": "S27d: event-level masked-window retraining for complete PID-energy-stress transformer eligibility",
    }
    (out / "REPORT.md").write_text(build_report(cfg, result, panel, window_attr, leakage, attention, repro, sources), encoding="utf-8")
    write_json(out / "result.json", result)

    manifest = {
        "ticket_id": cfg["ticket_id"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": result["git_commit"],
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "inputs": {
            "config": str(CONFIG.relative_to(ROOT)),
            "raw_root_dir": cfg["raw_root_dir"],
            **{k: v for k, v in cfg["sources"].items()},
        },
        "artifacts": {},
    }
    for path in sorted(out.iterdir()):
        if path.is_file():
            manifest["artifacts"][path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    write_json(out / "manifest.json", manifest)
    manifest["artifacts"]["manifest.json"] = {"bytes": (out / "manifest.json").stat().st_size, "sha256": sha256(out / "manifest.json")}
    write_json(out / "manifest.json", manifest)
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"winner {winner['method']} joint_loss={winner['joint_loss_score']:.6f}")


if __name__ == "__main__":
    main()
