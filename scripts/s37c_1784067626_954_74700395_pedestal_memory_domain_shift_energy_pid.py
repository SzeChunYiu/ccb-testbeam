#!/usr/bin/env python3
"""S37c pedestal-memory domain-shift audit for energy-PID pulse representations."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import s36d_1784065854_140549_01267a91_external_pid_pedestal_memory_benchmark as base  # noqa: E402
import t07_tradshape_ml_benchmark as t07  # noqa: E402


METHODS = base.METHODS


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def md_table(df: pd.DataFrame, columns: List[str], n: int | None = None) -> str:
    if df.empty:
        return "(empty)"
    view = df.loc[:, columns].copy()
    if n is not None:
        view = view.head(n)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "{:.5g}".format(x) if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def add_domain_strata(pred: pd.DataFrame, feats: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    rows = meta[["event_id", "source_run", "raw_selected_event_ordinal", "raw_selected_peak_adc", "truth_pileup_label", "truth_saturation_label", "truth_pedestal_adc"]].copy()
    rows["event_time_block"] = (
        rows.groupby("source_run")["raw_selected_event_ordinal"]
        .transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=["early", "middle", "late"], duplicates="drop"))
        .astype(str)
    )
    evaluated_events = set(pred["event_id"].unique())
    evaluated_rows = rows[rows["event_id"].isin(evaluated_events)]
    run_rate = evaluated_rows.groupby("source_run")["raw_selected_peak_adc"].median().rank(method="first")
    rate_map = pd.qcut(run_rate, 3, labels=["current_low", "current_mid", "current_high"], duplicates="drop").astype(str).to_dict()
    rows["current_rate_stratum"] = rows["source_run"].map(rate_map)
    rows["pileup_state"] = np.where(rows["truth_pileup_label"].to_numpy(int) > 0, "pileup_truth", "single_truth")
    rows["saturation_state"] = np.where(rows["truth_saturation_label"].to_numpy(int) > 0, "saturated_truth", "unsaturated_truth")
    rows["pedestal_truth_state"] = pd.qcut(np.abs(rows["truth_pedestal_adc"]), 3, labels=["pedestal_quiet", "pedestal_mid", "pedestal_memory"], duplicates="drop").astype(str)
    rows["late_tail_state"] = pd.qcut(feats["tail_12_17_over_total"], 3, labels=["tail_low", "tail_mid", "tail_high"], duplicates="drop").astype(str).to_numpy()
    return pred.merge(rows, on=["event_id", "source_run"], how="left")


def metric_or_empty(group: pd.DataFrame) -> Dict[str, float]:
    if group.empty or group["pid_label"].nunique() < 2:
        return {
            "pid_balanced_accuracy": float("nan"),
            "pid_auc": float("nan"),
            "pid_ece": float("nan"),
            "energy_fractional_sigma68": float("nan"),
            "energy_fractional_bias": float("nan"),
            "n_events": int(len(group)),
            "n_deuteron": int(group["pid_label"].sum()) if "pid_label" in group else 0,
        }
    return base.metric_values(group)


def block_bootstrap(group: pd.DataFrame, block_col: str, reps: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    blocks = np.asarray(sorted(group[block_col].dropna().unique()))
    if len(blocks) == 0:
        return pd.DataFrame()
    rows = []
    for _ in range(reps):
        sampled = rng.choice(blocks, size=len(blocks), replace=True)
        sample = pd.concat([group[group[block_col] == b] for b in sampled], ignore_index=True)
        vals = metric_or_empty(sample)
        for metric, value in vals.items():
            if isinstance(value, float) and np.isfinite(value):
                rows.append({"metric": metric, "value": float(value)})
    if not rows:
        return pd.DataFrame()
    boot = pd.DataFrame(rows)
    return boot.groupby("metric")["value"].quantile([0.025, 0.975]).unstack().reset_index().rename(columns={0.025: "ci_low", 0.975: "ci_high"})


def split_audits(pred: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    boot_rows = []
    split_defs = [
        ("run_held_out", "all", "source_run", None, None),
        ("time_blocked", "early", "source_run", "event_time_block", "early"),
        ("time_blocked", "middle", "source_run", "event_time_block", "middle"),
        ("time_blocked", "late", "source_run", "event_time_block", "late"),
        ("current_rate_stratified", "current_low", "source_run", "current_rate_stratum", "current_low"),
        ("current_rate_stratified", "current_mid", "source_run", "current_rate_stratum", "current_mid"),
        ("current_rate_stratified", "current_high", "source_run", "current_rate_stratum", "current_high"),
        ("pedestal_state", "pedestal_quiet", "source_run", "pedestal_truth_state", "pedestal_quiet"),
        ("pedestal_state", "pedestal_memory", "source_run", "pedestal_truth_state", "pedestal_memory"),
        ("pileup_leakage", "single_truth", "source_run", "pileup_state", "single_truth"),
        ("pileup_leakage", "pileup_truth", "source_run", "pileup_state", "pileup_truth"),
        ("saturation_interaction", "unsaturated_truth", "source_run", "saturation_state", "unsaturated_truth"),
        ("saturation_interaction", "saturated_truth", "source_run", "saturation_state", "saturated_truth"),
        ("late_tail_shape_drift", "tail_low", "source_run", "late_tail_state", "tail_low"),
        ("late_tail_shape_drift", "tail_high", "source_run", "late_tail_state", "tail_high"),
    ]
    reps = int(config["bootstrap_replicates"])
    for method, mg in pred.groupby("method", sort=True):
        for split_name, stratum, block_col, filter_col, filter_value in split_defs:
            group = mg if filter_col is None else mg[mg[filter_col] == filter_value]
            vals = metric_or_empty(group)
            row = {"method": method, "split": split_name, "stratum": stratum, "bootstrap_unit": block_col}
            row.update(vals)
            ci = block_bootstrap(group, block_col, reps, int(config["random_seed"]) + abs(hash((method, split_name, stratum))) % 100000)
            for _, cirow in ci.iterrows():
                metric = str(cirow["metric"])
                row[metric + "_ci_low"] = float(cirow["ci_low"])
                row[metric + "_ci_high"] = float(cirow["ci_high"])
                boot_rows.append({"method": method, "split": split_name, "stratum": stratum, "metric": metric, "ci_low": float(cirow["ci_low"]), "ci_high": float(cirow["ci_high"])})
            rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(boot_rows)


def permutation_controls(pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 909)
    rows = []
    for method, group in pred.groupby("method", sort=True):
        observed = metric_or_empty(group)
        for control in ["pid_permuted_within_run", "energy_permuted_within_run", "blocked_resampling_null"]:
            g = group.copy()
            if control == "pid_permuted_within_run":
                g["pid_label"] = g.groupby("source_run")["pid_label"].transform(lambda s: rng.permutation(s.to_numpy()))
            elif control == "energy_permuted_within_run":
                g["true_energy_mev"] = g.groupby("source_run")["true_energy_mev"].transform(lambda s: rng.permutation(s.to_numpy()))
            else:
                sampled = rng.choice(sorted(g["source_run"].unique()), size=g["source_run"].nunique(), replace=True)
                g = pd.concat([g[g["source_run"] == r] for r in sampled], ignore_index=True)
            vals = metric_or_empty(g)
            rows.append(
                {
                    "method": method,
                    "control": control,
                    "observed_pid_balanced_accuracy": observed["pid_balanced_accuracy"],
                    "control_pid_balanced_accuracy": vals["pid_balanced_accuracy"],
                    "observed_energy_fractional_sigma68": observed["energy_fractional_sigma68"],
                    "control_energy_fractional_sigma68": vals["energy_fractional_sigma68"],
                    "n_events": vals["n_events"],
                }
            )
    return pd.DataFrame(rows)


def domain_penalty(split_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in split_metrics.groupby("method", sort=True):
        pivot = group.set_index(["split", "stratum"])
        penalties = []
        for split_name in ["time_blocked", "current_rate_stratified", "pedestal_state", "pileup_leakage", "saturation_interaction", "late_tail_shape_drift"]:
            vals = pivot.loc[split_name]["energy_fractional_sigma68"].dropna() if split_name in pivot.index.get_level_values(0) else pd.Series(dtype=float)
            bacc = pivot.loc[split_name]["pid_balanced_accuracy"].dropna() if split_name in pivot.index.get_level_values(0) else pd.Series(dtype=float)
            if len(vals) > 1:
                penalties.append(float(vals.max() - vals.min()))
            if len(bacc) > 1:
                penalties.append(float(bacc.max() - bacc.min()))
        rows.append({"method": method, "domain_shift_penalty": float(np.nanmean(penalties)) if penalties else float("nan")})
    return pd.DataFrame(rows)


def summarize_with_domain(pred: pd.DataFrame, config: dict, cf: pd.DataFrame, split_metrics: pd.DataFrame) -> pd.DataFrame:
    summary, _, _ = base.summarize(pred, cf, config)
    summary = summary.drop(columns=["winner_score"], errors="ignore").merge(domain_penalty(split_metrics), on="method", how="left")
    w = config["winner_score_weights"]
    summary["winner_score"] = (
        w["pid_balanced_error"] * (1.0 - summary["pid_balanced_accuracy"])
        + w["energy_sigma68"] * summary["energy_fractional_sigma68"]
        + w["pedestal_counterfactual_span"] * summary["pedestal_counterfactual_span"]
        + w["pid_ece"] * summary["pid_ece"]
        + w["domain_shift_penalty"] * summary["domain_shift_penalty"]
    )
    return summary.sort_values("winner_score").reset_index(drop=True)


def write_report(out: Path, result: dict, summary: pd.DataFrame, split_metrics: pd.DataFrame, controls: pd.DataFrame, cf: pd.DataFrame, audit: pd.DataFrame, repro: pd.DataFrame, roles: pd.DataFrame) -> None:
    winner = result["winner"]["name"]
    lines = [
        "# S37c: Pedestal-Memory Domain Shift Audit for Energy-PID Pulse Representation",
        "",
        "## Abstract",
        "",
        "Ticket `{}` asks for a raw-ROOT-gated benchmark of a strong traditional pulse representation against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture under run-held-out, time-blocked, and current/rate-stratified uncertainty. The raw B-stack reproduction is exact at **{:,}** selected pulses. The external keyed GEANT4/digitized join supplies PID and energy labels for **{}** rows. The registered domain-shift score names **{}** as the winner.".format(result["ticket_id"], result["raw_root_reproduction"]["reproduced_selected_pulses"], result["external_join"]["joined_rows"], winner),
        "",
        "## Raw ROOT Reproduction",
        "",
        "Each `hrdb_run_NNNN.root` file is read from `h101/HRDv`. For channel `c`, the pedestal is `b_c=median(x_c(0),...,x_c(3))`; the baseline-subtracted waveform is `z_c(t)=x_c(t)-b_c`. A selected B-stave pulse satisfies `max_t z_c(t)>1000 ADC` for physical B2/B4/B6/B8 channels 0/2/4/6.",
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "## Labels and Join",
        "",
        "The modeling rows are the G4-08 native-key digitized rows joined by `(daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed, native_row)`. This keeps PID and energy labels external to event order and run labels.",
        "",
        md_table(audit, ["check", "value", "pass"]),
        "",
        "## Methods and Equations",
        "",
        "The traditional comparator, `traditional_ar1_deltaE_over_E`, uses a pedestal-memory AR(1) score",
        "",
        "`phi = sum_t Delta z_t Delta z_{t-1} / (sum_t Delta z_{t-1}^2 + epsilon)`,",
        "",
        "with innovation RMS, absolute/signed pedestal, charge, depth, and a dE/E proxy. It fits a balanced logistic PID model and log-linear energy model.",
        "",
        "The ML panel is ridge, histogram gradient-boosted trees, an extreme-learning ReLU MLP, and a 1D temporal-convolution feature bank. The new `pedestal_memory_gated_residual_cnn_new` gates temporal convolution channels with AR(1)/pedestal features and applies a boosted residual correction to log-energy. This is sensible for S37c because the target systematic is domain shift carried by pedestal memory, late tails, pile-up, and saturation.",
        "",
        "Primary residuals are `r_E=(E_hat-E_true)/E_true`; `sigma68(r)=0.5[Q84(r)-Q16(r)]`. PID calibration uses expected calibration error, `ECE=sum_b n_b/N |mean(p_b)-mean(y_b)|`. CIs are percentile intervals from block bootstraps over held-out runs, repeated for the split-specific strata.",
        "",
        "## Winner Table",
        "",
        md_table(summary, ["method", "winner_score", "pid_auc", "pid_balanced_accuracy", "pid_balanced_accuracy_ci_low", "pid_balanced_accuracy_ci_high", "pid_ece", "energy_fractional_sigma68", "energy_fractional_sigma68_ci_low", "energy_fractional_sigma68_ci_high", "pedestal_counterfactual_span", "domain_shift_penalty"]),
        "",
        "## Split-Specific Systematics",
        "",
        "The table reports the full method panel under run-held-out, time-blocked event-order, current/rate proxy, pedestal-memory, pile-up, saturation, and late-tail strata. Bootstrap units remain runs, so the intervals preserve run-level domain shift.",
        "",
        md_table(split_metrics, ["method", "split", "stratum", "pid_balanced_accuracy", "pid_balanced_accuracy_ci_low", "pid_balanced_accuracy_ci_high", "energy_fractional_sigma68", "energy_fractional_sigma68_ci_low", "energy_fractional_sigma68_ci_high", "n_events"], n=120),
        "",
        "## Permutation and Blocked Controls",
        "",
        "PID labels and energy labels are permuted within run as negative controls; the blocked-resampling null repeats the run bootstrap without changing labels. A model that remains strong under label permutation would be treated as acquisition-state leakage rather than pulse physics.",
        "",
        md_table(controls, ["method", "control", "observed_pid_balanced_accuracy", "control_pid_balanced_accuracy", "observed_energy_fractional_sigma68", "control_energy_fractional_sigma68", "n_events"]),
        "",
        "## Pedestal Counterfactuals",
        "",
        md_table(cf, ["method", "pedestal_state", "mean_pid_score", "counterfactual_span"]),
        "",
        "## Caveats",
        "",
        "- The raw selected-pulse count is a full ROOT reproduction, but the external PID/energy benchmark is limited to the 1,056 keyed digitized rows.",
        "- Current/rate is a run-level proxy built from held-out peak occupancy and sample grouping; it is not an independent scaler readback.",
        "- Time-blocked strata use event order within run, so they diagnose acquisition drift but not absolute wall-clock time.",
        "- The digitized GEANT4 bridge supplies truth labels and controlled pedestal states, but it is still a hybrid detector-response artifact.",
        "- Run-block bootstrap covers observed runs only; unobserved beamline states and future electronics settings are outside these CIs.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s37c_1784067626_954_74700395_pedestal_memory_domain_shift_energy_pid.py --config configs/s37c_1784067626_954_74700395_pedestal_memory_domain_shift_energy_pid.json",
        "```",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s37c_1784067626_954_74700395_pedestal_memory_domain_shift_energy_pid.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_json(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    raw_dir = t07.resolve_raw_root_dir(config)
    expected = int(config["expected_total_selected_pulses"])
    if (out / "reproduction_match_table.csv").exists() and (out / "reproduction_counts_by_run.csv").exists():
        repro = pd.read_csv(out / "reproduction_match_table.csv")
        selected = int(repro["reproduced"].iloc[0])
    else:
        raw_waves, raw_meta, counts = t07.scan_raw(config, raw_dir)
        selected = int(len(raw_waves))
        if selected != expected:
            raise RuntimeError("raw ROOT reproduction failed: {} != {}".format(selected, expected))
        counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
        repro = pd.DataFrame([{"quantity": "total selected B-stave pulses", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}])
        repro.to_csv(out / "reproduction_match_table.csv", index=False)

    waves, meta, audit = base.load_external_join(config)
    audit.to_csv(out / "external_native_join_audit.csv", index=False)
    feats, roles, strata = base.build_features(waves, meta, config)
    feats.to_csv(out / "external_join_features.csv.gz", index=False)
    roles.to_csv(out / "feature_family_audit.csv", index=False)
    strata.to_csv(out / "strata_assignments.csv", index=False)

    pred = base.fit_methods(waves, feats, meta, config)
    cf = base.pedestal_counterfactuals(pred, feats, meta)
    pred = add_domain_strata(pred, feats, meta)
    pred.to_csv(out / "heldout_predictions.csv.gz", index=False)
    cf.to_csv(out / "pedestal_counterfactuals.csv", index=False)
    split_metrics, split_boot = split_audits(pred, config)
    split_metrics.to_csv(out / "split_systematic_metrics.csv", index=False)
    split_boot.to_csv(out / "split_bootstrap_intervals_long.csv", index=False)
    controls = permutation_controls(pred, config)
    controls.to_csv(out / "permutation_block_controls.csv", index=False)
    summary = summarize_with_domain(pred, config, cf, split_metrics)
    summary.to_csv(out / "method_summary.csv", index=False)

    winner = summary.iloc[0].to_dict()
    trad = summary[summary["method"] == "traditional_ar1_deltaE_over_E"].iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "claimed_ticket_text": "S37c: pedestal-memory domain shift audit for energy-PID pulse representation",
        "study_id": config["study_id"],
        "project": "testbeam",
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "raw_root_reproduction": {
            "passed": selected == expected,
            "raw_root_dir": str(raw_dir),
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": selected,
            "delta": selected - expected
        },
        "external_join": {
            "source_report_dir": config["g4_join_report_dir"],
            "joined_rows": int(len(meta)),
            "audit_passed": bool(audit["pass"].all())
        },
        "splits": {
            "run_held_out": {"train_runs": [int(r) for r in config["train_runs"]], "heldout_runs": [int(r) for r in config["heldout_runs"]], "bootstrap_unit": "source_run"},
            "time_blocked": "early/middle/late by raw_selected_event_ordinal within held-out run",
            "current_rate_stratified": "held-out source_run tertiles by median raw_selected_peak_adc",
            "bootstrap_replicates": int(config["bootstrap_replicates"])
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_ar1_deltaE_over_E",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "pedestal_memory_gated_residual_cnn_new"
        },
        "winner": {
            "name": str(winner["method"]),
            "criterion": "minimum S37c domain-shift score across PID, energy, pedestal sensitivity, calibration, and split instability",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_balanced_accuracy": float(winner["pid_balanced_accuracy"]),
            "pid_balanced_accuracy_ci95": [float(winner["pid_balanced_accuracy_ci_low"]), float(winner["pid_balanced_accuracy_ci_high"])],
            "energy_fractional_sigma68": float(winner["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [float(winner["energy_fractional_sigma68_ci_low"]), float(winner["energy_fractional_sigma68_ci_high"])],
            "pedestal_counterfactual_span": float(winner["pedestal_counterfactual_span"]),
            "domain_shift_penalty": float(winner["domain_shift_penalty"])
        },
        "traditional_comparator": json_clean(trad),
        "controls": {
            "permutation_controls": "permutation_block_controls.csv",
            "blocked_resampling": "split_bootstrap_intervals_long.csv"
        },
        "systematics_covered": [
            "pedestal memory",
            "late-tail shape drift",
            "pile-up leakage",
            "timing/acquisition order bias",
            "saturation interactions",
            "energy calibration transfer",
            "PID confusion"
        ],
        "novel_tickets_appended": [
            {
                "ticket_id": "1784068210.870.38ff282e",
                "title": "testbeam-laptop-1",
                "body": "",
                "note": "The local tn-ticket shim accepted the first positional argument as the title; no second ticket was appended because the objective limits this run to at most one appended ticket."
            }
        ],
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "method_summary": "method_summary.csv",
            "split_systematic_metrics": "split_systematic_metrics.csv",
            "permutation_block_controls": "permutation_block_controls.csv",
            "heldout_predictions": "heldout_predictions.csv.gz",
            "reproduction_match_table": "reproduction_match_table.csv"
        },
        "runtime_sec": time.time() - t0,
        "git_commit": git_commit(),
        "python": platform.python_version()
    }
    (out / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out, result, summary, split_metrics, controls, cf, audit, repro, roles)

    manifest = {"ticket_id": config["ticket_id"], "generated_at_unix": time.time(), "command": " ".join(sys.argv), "artifacts": []}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["artifacts"].append({"path": str(path.relative_to(ROOT)), "sha256": base.sha256_file(path), "bytes": int(path.stat().st_size)})
    (out / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
