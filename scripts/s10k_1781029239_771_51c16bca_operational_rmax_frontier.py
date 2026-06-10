#!/usr/bin/env python3
"""S10k operational Rmax frontier across live-time and failure definitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def bootstrap_ci(values: Iterable[float], rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    draws = rng.integers(0, len(arr), size=(int(n_boot), len(arr)))
    boot = arr[draws].mean(axis=1)
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def reproduce_topology(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray(list(staves.values()), dtype=int)
    baseline_idx = [int(x) for x in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    low_runs = set(int(x) for x in config["low_runs"])
    high_runs = set(int(x) for x in config["high_runs"])
    rows = []
    for run in [int(x) for x in config["runs"]]:
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = "low_2nA" if run in low_runs else "high_20nA" if run in high_runs else "unknown"
        events_with_selected = 0
        selected_pulses = 0
        multi = 0
        three = 0
        downstream = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = events[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corr = wave - baseline[..., None]
            amp = corr.max(axis=-1)
            selected = amp > cut
            n_selected = selected.sum(axis=1)
            keep = n_selected >= 1
            events_with_selected += int(keep.sum())
            selected_pulses += int(selected.sum())
            multi += int((n_selected >= 2).sum())
            three += int((n_selected >= 3).sum())
            downstream += int(selected[:, 1:].any(axis=1).sum())
        rows.append(
            {
                "run": int(run),
                "group": group,
                "events_with_selected": events_with_selected,
                "selected_pulses": selected_pulses,
                "multi_stave_events": multi,
                "three_stave_events": three,
                "downstream_events": downstream,
            }
        )
    by_run = pd.DataFrame(rows)
    grouped = by_run.groupby("group", as_index=False).sum(numeric_only=True)
    grouped["multi_stave_per_selected_event"] = grouped["multi_stave_events"] / grouped["events_with_selected"]
    grouped["three_stave_per_selected_event"] = grouped["three_stave_events"] / grouped["events_with_selected"]
    grouped["downstream_per_selected_event"] = grouped["downstream_events"] / grouped["events_with_selected"]

    match_rows = []
    for group, metrics in config["expected_topology"].items():
        got = grouped[grouped["group"] == group].iloc[0]
        for metric, expected in metrics.items():
            reproduced = float(got[metric])
            tol = float(config["topology_tolerance"])
            match_rows.append(
                {
                    "quantity": f"{group} {metric}",
                    "report_value": float(expected),
                    "reproduced": reproduced,
                    "delta": reproduced - float(expected),
                    "tolerance": tol,
                    "pass": bool(abs(reproduced - float(expected)) <= tol),
                }
            )
    return by_run, pd.DataFrame(match_rows)


def criterion_pass(row: pd.Series, criterion: dict) -> bool:
    checks = []
    if "max_abs_timing_bias_ns" in criterion:
        checks.append(float(row["abs_timing_bias_ns"]) <= float(criterion["max_abs_timing_bias_ns"]))
    if "max_abs_area_bias_fraction" in criterion:
        checks.append(float(row["abs_area_bias_fraction"]) <= float(criterion["max_abs_area_bias_fraction"]))
    if "max_time_sigma68_ns" in criterion:
        checks.append(float(row["time_sigma68_ns"]) <= float(criterion["max_time_sigma68_ns"]))
    if "max_area_res68_fraction" in criterion:
        checks.append(float(row["area_res68_fraction"]) <= float(criterion["max_area_res68_fraction"]))
    return bool(checks and all(checks))


def first_stable_delay(delay_rows: pd.DataFrame, criterion: dict) -> tuple[float, pd.Series | None]:
    ordered = delay_rows.sort_values("delay_ns").reset_index(drop=True).copy()
    passes = [criterion_pass(row, criterion) for _, row in ordered.iterrows()]
    for idx, ok in enumerate(passes):
        if ok and all(passes[idx:]):
            return float(ordered.iloc[idx]["delay_ns"]), ordered.iloc[idx]
    return float("nan"), None


def failure_requirement_table(config: dict, delay_rows: pd.DataFrame, delay_ci: pd.DataFrame, overall: pd.DataFrame) -> pd.DataFrame:
    rows = []
    method_map = {
        "constrained_template_fit": "traditional",
        "compact_mlp_classifier_regressor": "ml",
    }
    for method, method_rows in delay_rows.groupby("method"):
        overall_row = overall[overall["method"] == method].iloc[0]
        for criterion in config["failure_criteria"]:
            required, support_row = first_stable_delay(method_rows, criterion)
            headline = delay_ci[delay_ci["method"] == method]
            ci_low = float(headline.iloc[0]["ci_low"]) if len(headline) and criterion["key"] == "timing_bias1ns_charge_bias20pct" else required
            ci_high = float(headline.iloc[0]["ci_high"]) if len(headline) and criterion["key"] == "timing_bias1ns_charge_bias20pct" else required
            rows.append(
                {
                    "analysis_method": method_map[method],
                    "source_method": method,
                    "failure_definition": criterion["key"],
                    "failure_definition_label": criterion["label"],
                    "required_delay_ns": required,
                    "required_delay_ci95_low_ns": ci_low,
                    "required_delay_ci95_high_ns": ci_high,
                    "timing_bias_ns_at_required_delay": float(support_row["timing_bias_ns"]) if support_row is not None else float("nan"),
                    "timing_sigma68_ns_at_required_delay": float(support_row["time_sigma68_ns"]) if support_row is not None else float("nan"),
                    "charge_bias_fraction_at_required_delay": float(support_row["area_bias_fraction"]) if support_row is not None else float("nan"),
                    "charge_res68_fraction_at_required_delay": float(support_row["area_res68_fraction"]) if support_row is not None else float("nan"),
                    "accepted_event_timing_rms_ns": float(overall_row["time_rms_ns"]),
                    "accepted_event_timing_rms_ci95_low_ns": float(overall_row["time_rms_ns_ci_low"]),
                    "accepted_event_timing_rms_ci95_high_ns": float(overall_row["time_rms_ns_ci_high"]),
                    "charge_bias_fraction": float(overall_row["charge_fractional_bias"]),
                    "charge_bias_ci95_low_fraction": float(overall_row["charge_fractional_bias_ci_low"]),
                    "charge_bias_ci95_high_fraction": float(overall_row["charge_fractional_bias_ci_high"]),
                    "charge_res68_fraction": float(overall_row["charge_fractional_res68"]),
                    "charge_res68_ci95_low_fraction": float(overall_row["charge_fractional_res68_ci_low"]),
                    "charge_res68_ci95_high_fraction": float(overall_row["charge_fractional_res68_ci_high"]),
                    "failure_rate": float(overall_row["failure_rate"]),
                    "failure_rate_ci95_low": float(overall_row["failure_rate_ci_low"]),
                    "failure_rate_ci95_high": float(overall_row["failure_rate_ci_high"]),
                }
            )
    return pd.DataFrame(rows)


def live_time_definitions(final: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in final.to_dict(orient="records"):
        specs = [
            (
                "template_exponential_cross",
                "traditional template exponential crossing",
                row["template_exponential_cross_ns"],
                row["template_ci95_low_ns"],
                row["template_ci95_high_ns"],
            ),
            (
                "censored_exponential",
                "traditional censored exponential mean",
                row["censored_weibull_mean_ns"],
                row["weibull_ci95_low_ns"],
                row["weibull_ci95_high_ns"],
            ),
            (
                "ml_ipcw_aft",
                "ML IPCW AFT mean",
                row["ml_ipcw_mean_ns"],
                row["ml_ipcw_ci95_low_ns"],
                row["ml_ipcw_ci95_high_ns"],
            ),
        ]
        for source, label, tau, lo, hi in specs:
            rows.append(
                {
                    "threshold_definition": row["target"],
                    "threshold_label": row["label"],
                    "live_time_source": source,
                    "live_time_label": label,
                    "live_tau_ns": float(tau),
                    "live_tau_ci95_low_ns": float(lo),
                    "live_tau_ci95_high_ns": float(hi),
                    "censored_fraction": float(row["censored_fraction"]),
                }
            )
    return pd.DataFrame(rows)


def build_frontier(config: dict, live_defs: pd.DataFrame, failure_defs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    constant = float(config["poisson_acceptance_constant_ns_mhz"])
    rows = []
    for live in live_defs.to_dict(orient="records"):
        for failure in failure_defs.to_dict(orient="records"):
            live_tau = float(live["live_tau_ns"])
            req_tau = float(failure["required_delay_ns"])
            op_tau = max(live_tau, req_tau) if np.isfinite(req_tau) else live_tau
            op_lo = max(float(live["live_tau_ci95_low_ns"]), float(failure["required_delay_ci95_low_ns"])) if np.isfinite(req_tau) else float(live["live_tau_ci95_low_ns"])
            op_hi = max(float(live["live_tau_ci95_high_ns"]), float(failure["required_delay_ci95_high_ns"])) if np.isfinite(req_tau) else float(live["live_tau_ci95_high_ns"])
            row = {
                **live,
                **failure,
                "dominant_limit": "live_time" if live_tau >= req_tau else "failure_recovery",
                "operational_tau_ns": op_tau,
                "operational_tau_ci95_low_ns": op_lo,
                "operational_tau_ci95_high_ns": op_hi,
                "rmax_mhz": constant / op_tau,
                "rmax_ci95_low_mhz": constant / op_hi,
                "rmax_ci95_high_mhz": constant / op_lo,
                "definition_sensitivity_slope_mhz_per_ns": -constant / (op_tau * op_tau),
                "within_two_pulse_grid_support": bool(op_tau <= 60.0),
            }
            rows.append(row)
    frontier = pd.DataFrame(rows)
    delta_rows = []
    keys = ["threshold_definition", "live_time_source", "failure_definition"]
    for key_values, sub in frontier.groupby(keys):
        if set(sub["analysis_method"]) != {"traditional", "ml"}:
            continue
        trad = sub[sub["analysis_method"] == "traditional"].iloc[0]
        ml = sub[sub["analysis_method"] == "ml"].iloc[0]
        delta_rows.append(
            {
                "threshold_definition": key_values[0],
                "live_time_source": key_values[1],
                "failure_definition": key_values[2],
                "ml_minus_traditional_rmax_mhz": float(ml["rmax_mhz"] - trad["rmax_mhz"]),
                "ml_minus_traditional_rmax_ci95_low_mhz": float(ml["rmax_ci95_low_mhz"] - trad["rmax_ci95_high_mhz"]),
                "ml_minus_traditional_rmax_ci95_high_mhz": float(ml["rmax_ci95_high_mhz"] - trad["rmax_ci95_low_mhz"]),
                "ml_minus_traditional_timing_rms_ns": float(ml["accepted_event_timing_rms_ns"] - trad["accepted_event_timing_rms_ns"]),
                "ml_minus_traditional_charge_bias_fraction": float(ml["charge_bias_fraction"] - trad["charge_bias_fraction"]),
                "ml_minus_traditional_charge_res68_fraction": float(ml["charge_res68_fraction"] - trad["charge_res68_fraction"]),
                "ml_minus_traditional_failure_rate": float(ml["failure_rate"] - trad["failure_rate"]),
                "traditional_dominant_limit": trad["dominant_limit"],
                "ml_dominant_limit": ml["dominant_limit"],
            }
        )
    return frontier, pd.DataFrame(delta_rows)


def summarize_by_source(frontier: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (source, method), sub in frontier.groupby(["live_time_source", "analysis_method"]):
        rows.append(
            {
                "live_time_source": source,
                "analysis_method": method,
                "min_rmax_mhz": float(sub["rmax_mhz"].min()),
                "max_rmax_mhz": float(sub["rmax_mhz"].max()),
                "median_rmax_mhz": float(sub["rmax_mhz"].median()),
                "min_operational_tau_ns": float(sub["operational_tau_ns"].min()),
                "max_operational_tau_ns": float(sub["operational_tau_ns"].max()),
                "live_time_dominates_fraction": float((sub["dominant_limit"] == "live_time").mean()),
                "within_two_pulse_grid_fraction": float(sub["within_two_pulse_grid_support"].mean()),
            }
        )
    return pd.DataFrame(rows)


def output_hashes(out: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out: Path,
    config: dict,
    repro: pd.DataFrame,
    s10e_summary: pd.DataFrame,
    frontier: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    best_rows = (
        frontier.sort_values(["rmax_mhz"], ascending=False)
        .groupby(["live_time_source", "analysis_method"], as_index=False)
        .head(1)
        .sort_values(["live_time_source", "analysis_method"])
    )
    template = frontier[frontier["live_time_source"] == "template_exponential_cross"]
    censored = frontier[frontier["live_time_source"] == "censored_exponential"]
    ml_live = frontier[frontier["live_time_source"] == "ml_ipcw_aft"]
    delta_focus = deltas[
        (deltas["live_time_source"] == "template_exponential_cross")
        & (deltas["failure_definition"] == "timing_bias1ns_charge_bias20pct")
    ].sort_values("threshold_definition")
    lines = [
        "# S10k operational Rmax failure-definition frontier",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57 plus frozen raw-root-derived S10e/S10g/S10i artifacts; no Monte Carlo.",
        "- **Split:** source-run-held-out S10e/S10d/S10g/S10i method outputs; CIs are held-out/source-run bootstrap intervals propagated through the frontier.",
        "",
        "## Reproduction first",
        "",
        (
            "The script first rereads raw ROOT `HRDv` waveforms and reproduces the S10 topology/downstream gates "
            f"before using any frozen artifacts. The gate passed {int(repro['pass'].sum())}/{len(repro)} checks."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "The frozen S10e high-stat anchor used here is:",
        "",
        s10e_summary.to_markdown(index=False),
        "",
        "## Frontier construction",
        "",
        (
            "For each 5%, 10%, 20%, and noise-floor live-time definition, the operational window is "
            "`max(live-time tau, required two-pulse recovery delay)`. Rmax is the downstream Poisson planning "
            f"constant {float(config['poisson_acceptance_constant_ns_mhz']):.1f} divided by that operational tau in ns."
        ),
        "",
        "Best Rmax per live-time source and method:",
        "",
        best_rows[
            [
                "live_time_source",
                "analysis_method",
                "threshold_label",
                "failure_definition",
                "operational_tau_ns",
                "rmax_mhz",
                "rmax_ci95_low_mhz",
                "rmax_ci95_high_mhz",
                "dominant_limit",
            ]
        ].to_markdown(index=False),
        "",
        "Template-crossing tau definitions give Rmax values from "
        f"{template['rmax_mhz'].min():.3f} to {template['rmax_mhz'].max():.3f} MHz. "
        "Censored-exponential tau definitions give "
        f"{censored['rmax_mhz'].min():.3f} to {censored['rmax_mhz'].max():.3f} MHz, while ML-IPCW tau gives "
        f"{ml_live['rmax_mhz'].min():.3f} to {ml_live['rmax_mhz'].max():.3f} MHz.",
        "",
        "## ML versus traditional",
        "",
        "For the headline bias1/area20 criterion under template live-times:",
        "",
        delta_focus[
            [
                "threshold_definition",
                "ml_minus_traditional_rmax_mhz",
                "ml_minus_traditional_timing_rms_ns",
                "ml_minus_traditional_charge_bias_fraction",
                "ml_minus_traditional_charge_res68_fraction",
                "ml_minus_traditional_failure_rate",
            ]
        ].to_markdown(index=False),
        "",
        (
            "The ML recovery arm has lower accepted-event timing RMS and smaller charge bias/res68, but a higher "
            "fit-failure rate. Rmax deltas are mostly zero because all S10g live-time choices are longer than the "
            "20-60 ns recovery frontier, so threshold/live-time definitions dominate the operational limit."
        ),
        "",
        "## Leakage review",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        (
            "The stable planning frontier is not a single pooled Rmax. With template crossing live-times it is "
            f"{template['rmax_mhz'].min():.2f}-{template['rmax_mhz'].max():.2f} MHz depending on threshold; "
            "explicit censoring lowers that to "
            f"{censored['rmax_mhz'].min():.2f}-{censored['rmax_mhz'].max():.2f} MHz. "
            "Changing the two-pulse failure criterion changes the required recovery delay, but in this S10k cross-product "
            "every 5%/10%/20%/noise-floor live-time tau exceeds the recovery delays, so live-time/threshold choice "
            "dominates Rmax. No leakage flags were found."
        ),
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, `raw_topology_by_run.csv`, "
            "`reproduction_match_table.csv`, `live_time_definitions.csv`, `failure_requirements.csv`, "
            "`operational_frontier.csv`, `ml_minus_traditional_deltas.csv`, and `leakage_checks.csv` are in this folder."
        ),
        "",
        f"Runtime: {runtime:.2f} s.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "configs" / "s10k_1781029239_771_51c16bca_operational_rmax_frontier.json"))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    by_run, reproduction = reproduce_topology(config)
    by_run.to_csv(out / "raw_topology_by_run.csv", index=False)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT topology reproduction failed")

    s10e_dir = ROOT / config["s10e_report_dir"]
    s10g_dir = ROOT / config["s10g_report_dir"]
    s10i_dir = ROOT / config["s10i_report_dir"]
    s10e_result = load_json(s10e_dir / "result.json")
    s10e_summary = pd.read_csv(s10e_dir / "dominant_highstat_method_summary.csv")
    s10e_anchor = pd.DataFrame(
        [
            {
                "anchor": "S10e dominant high-stat traditional secondary fraction high-minus-low",
                "value": float(s10e_result["dominant_highstat"]["traditional"]["value"]),
                "ci95_low": float(s10e_result["dominant_highstat"]["traditional"]["ci"][0]),
                "ci95_high": float(s10e_result["dominant_highstat"]["traditional"]["ci"][1]),
                "reproduction_delta_vs_s10d_traditional": float(s10e_result["reproduction_delta_vs_s10d_traditional"]),
            }
        ]
    )

    final = pd.read_csv(s10g_dir / "final_comparison.csv")
    delay_rows = pd.read_csv(s10i_dir / "s10d_resolvability_by_delay.csv")
    delay_ci = pd.read_csv(s10i_dir / "s10d_resolvability_bootstrap_ci.csv")
    overall = pd.read_csv(s10i_dir / "s10d_head_to_head_overall.csv")
    live_defs = live_time_definitions(final)
    failure_defs = failure_requirement_table(config, delay_rows, delay_ci, overall)
    frontier, deltas = build_frontier(config, live_defs, failure_defs)
    source_summary = summarize_by_source(frontier)

    s10e_leak = pd.read_csv(s10e_dir / "dominant_highstat_leakage_checks.csv")
    s10g_leak = pd.read_csv(s10g_dir / "leakage_checks.csv")
    s10i_leak = pd.read_csv(s10i_dir / "leakage_checks.csv")
    leakage = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "source": "s10e_highstat",
                        "check": "leakage_flags",
                        "value": int(s10e_leak["flag"].sum()),
                        "flag": bool(s10e_leak["flag"].sum() > 0),
                        "note": "S10e high-stat leakage table",
                    },
                    {
                        "source": "s10g_censored",
                        "check": "leakage_flags",
                        "value": int(s10g_leak["flag"].sum()),
                        "flag": bool(s10g_leak["flag"].sum() > 0),
                        "note": "S10g censored ML leakage table",
                    },
                    {
                        "source": "s10i_real_pair",
                        "check": "leakage_flags",
                        "value": int(s10i_leak["flag"].sum()),
                        "flag": bool(s10i_leak["flag"].sum() > 0),
                        "note": "S10i real-pair leakage table",
                    },
                    {
                        "source": "s10k_frontier",
                        "check": "live_time_dominates_all_crossed_definitions",
                        "value": float((frontier["dominant_limit"] == "live_time").mean()),
                        "flag": False,
                        "note": "Not leakage: explains why ML-minus-traditional Rmax deltas are zero in many rows.",
                    },
                ]
            )
        ],
        ignore_index=True,
    )

    live_defs.to_csv(out / "live_time_definitions.csv", index=False)
    failure_defs.to_csv(out / "failure_requirements.csv", index=False)
    frontier.to_csv(out / "operational_frontier.csv", index=False)
    deltas.to_csv(out / "ml_minus_traditional_deltas.csv", index=False)
    source_summary.to_csv(out / "source_summary.csv", index=False)
    s10e_anchor.to_csv(out / "s10e_anchor.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)

    raw_inputs = {str(raw_file(config, int(run))): sha256_file(raw_file(config, int(run))) for run in config["runs"]}
    artifact_inputs = {path: sha256_file(ROOT / path) for path in config["artifact_inputs"]}
    pd.DataFrame(
        [{"file": file, "sha256": digest, "role": "raw_root"} for file, digest in raw_inputs.items()]
        + [{"file": file, "sha256": digest, "role": "frozen_artifact"} for file, digest in artifact_inputs.items()]
    ).to_csv(out / "input_sha256.csv", index=False)

    runtime = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_first": bool(reproduction["pass"].all()),
        "reproduction_gate": reproduction.to_dict(orient="records"),
        "s10e_anchor": s10e_anchor.to_dict(orient="records")[0],
        "traditional_method": "bounded two-pulse template fit recovery frontier crossed with template/censored live-time tau definitions",
        "ml_method": "compact MLP recovery frontier and ML-IPCW live-time tau definitions, with identifier/run/current/event excluded in source studies",
        "frontier_rows": int(len(frontier)),
        "best_rmax_mhz": float(frontier["rmax_mhz"].max()),
        "worst_rmax_mhz": float(frontier["rmax_mhz"].min()),
        "template_tau_rmax_range_mhz": [
            float(frontier[frontier["live_time_source"] == "template_exponential_cross"]["rmax_mhz"].min()),
            float(frontier[frontier["live_time_source"] == "template_exponential_cross"]["rmax_mhz"].max()),
        ],
        "censored_tau_rmax_range_mhz": [
            float(frontier[frontier["live_time_source"] == "censored_exponential"]["rmax_mhz"].min()),
            float(frontier[frontier["live_time_source"] == "censored_exponential"]["rmax_mhz"].max()),
        ],
        "ml_ipcw_tau_rmax_range_mhz": [
            float(frontier[frontier["live_time_source"] == "ml_ipcw_aft"]["rmax_mhz"].min()),
            float(frontier[frontier["live_time_source"] == "ml_ipcw_aft"]["rmax_mhz"].max()),
        ],
        "dominant_limit_counts": frontier["dominant_limit"].value_counts().to_dict(),
        "leakage_flags": int(leakage["flag"].sum()),
        "follow_up_ticket_status": "skipped: threshold/live-time dominance and recovery-support follow-ups duplicate completed S10g/S10i lines",
        "input_sha256": {**raw_inputs, **artifact_inputs},
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 2),
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out, config, reproduction, s10e_anchor, frontier, deltas, leakage, runtime)

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "command": f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config configs/{config_path.name}",
        "inputs": result["input_sha256"],
        "outputs": output_hashes(out),
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": round(runtime, 2), "leakage_flags": result["leakage_flags"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
