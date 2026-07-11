#!/usr/bin/env python3
"""P12f arbitration-threshold frontier under sample-family drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p12a_1781023340_632_43377364_pulse_axis_covariance as p12a  # noqa: E402


HARM_COLS = [
    "harm_timing",
    "harm_charge",
    "harm_saturation",
    "harm_pileup",
    "harm_baseline",
    "harm_dropout",
    "harm_pid",
    "harm_energy",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def ci(values: Iterable[float]) -> List[float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def parse_config_cell(cell: str, key: str) -> str:
    parts = str(cell).split("|")
    for part in parts:
        if part.startswith(key):
            return part
    return "missing"


def prepare_policy_frame(config: dict) -> pd.DataFrame:
    df = pd.read_csv(config["p12e_predictions"])
    needed = {"run", "group", "stave", "any_consumer_harm", "consumer_harm_count", *HARM_COLS}
    missing = sorted(needed.difference(df.columns))
    if missing:
        raise RuntimeError("P12e prediction table missing columns: {}".format(missing))
    for method in config["methods"]:
        if method["risk_col"] not in df.columns:
            raise RuntimeError("Missing risk column {}".format(method["risk_col"]))
    df["any_consumer_harm"] = df["any_consumer_harm"].astype(int)
    df["consumer_harm_count"] = df["consumer_harm_count"].astype(float)
    df["sample_family"] = df["group"].map(
        {"sample_i_calib": "Sample-I", "sample_i_analysis": "Sample-I", "sample_ii_calib": "Sample-II", "sample_ii_analysis": "Sample-II"}
    ).fillna("unknown")
    df["amplitude_bin"] = df["atom_action_band"].map(lambda x: parse_config_cell(x, "amp_"))
    df["shape_bin"] = df["atom_action_band"].map(lambda x: parse_config_cell(x, "shape_"))
    df["support_bin"] = df["stave"].astype(str) + "|" + df["amplitude_bin"].astype(str) + "|" + df["shape_bin"].astype(str)
    return df


def metric_for(frame: pd.DataFrame, risk_col: str, coverage: float) -> dict:
    risk = frame[risk_col].to_numpy(dtype=float)
    threshold = float(np.quantile(risk, float(coverage)))
    accepted = risk <= threshold
    rejected = ~accepted
    harm = frame["any_consumer_harm"].to_numpy(dtype=float)
    harm_count = frame["consumer_harm_count"].to_numpy(dtype=float)
    total_harm = float(harm_count.sum())
    accepted_harm = float(harm[accepted].mean()) if accepted.any() else np.nan
    accepted_harm_count = float(harm_count[accepted].mean()) if accepted.any() else np.nan
    rejected_harm_capture = float(harm_count[rejected].sum() / total_harm) if total_harm > 0 and rejected.any() else 0.0
    harmful_rejected = float(harm[rejected].sum() / max(harm.sum(), 1.0)) if rejected.any() else 0.0
    accepted_support = float(accepted.mean())
    loss = accepted_harm + (1.0 - rejected_harm_capture)
    return {
        "threshold": threshold,
        "accepted_support": accepted_support,
        "rejected_support": float(rejected.mean()),
        "accepted_harm_rate": accepted_harm,
        "accepted_harm_count_mean": accepted_harm_count,
        "rejected_harm_capture": rejected_harm_capture,
        "harmful_pulse_rejection": harmful_rejected,
        "policy_loss": float(loss),
    }


def method_frontier(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    by_run_rows = []
    stave_rows = []
    for method in config["methods"]:
        for coverage in config["benchmark"]["coverage_grid"]:
            row = {
                "method": method["method"],
                "family": method["family"],
                "coverage": float(coverage),
                **metric_for(df, method["risk_col"], float(coverage)),
            }
            rows.append(row)
            for run, part in df.groupby("run"):
                by_run_rows.append(
                    {
                        "run": int(run),
                        "method": method["method"],
                        "family": method["family"],
                        "coverage": float(coverage),
                        **metric_for(part, method["risk_col"], float(coverage)),
                    }
                )
            threshold = row["threshold"]
            accepted = df[df[method["risk_col"]] <= threshold]
            for stave, part in accepted.groupby("stave"):
                stave_rows.append(
                    {
                        "method": method["method"],
                        "family": method["family"],
                        "coverage": float(coverage),
                        "stave": stave,
                        "accepted_n": int(len(part)),
                        "accepted_fraction_within_accepted": float(len(part) / max(len(accepted), 1)),
                        "accepted_harm_rate": float(part["any_consumer_harm"].mean()),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(by_run_rows), pd.DataFrame(stave_rows)


def run_bootstrap(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    runs = sorted(int(x) for x in df["run"].unique())
    run_to_idx = {run: idx for idx, run in enumerate(runs)}
    run_idx = df["run"].map(run_to_idx).to_numpy(dtype=int)
    harm = df["any_consumer_harm"].to_numpy(dtype=float)
    harm_count = df["consumer_harm_count"].to_numpy(dtype=float)
    reps = int(config["benchmark"]["bootstrap_reps"])
    coverages = [float(x) for x in config["benchmark"]["coverage_grid"]]
    rows = []
    for method in config["methods"]:
        risk = df[method["risk_col"]].to_numpy(dtype=float)
        order = np.argsort(risk, kind="mergesort")
        risk_s = risk[order]
        run_s = run_idx[order]
        harm_s = harm[order]
        count_s = harm_count[order]
        values_by_coverage: Dict[float, Dict[str, list]] = {
            coverage: {
                "policy_loss": [],
                "accepted_harm_rate": [],
                "rejected_harm_capture": [],
                "harmful_pulse_rejection": [],
                "accepted_support": [],
                "threshold": [],
            }
            for coverage in coverages
        }
        for _ in range(reps):
            sampled_runs = rng.choice(runs, size=len(runs), replace=True)
            run_counts = np.bincount([run_to_idx[int(r)] for r in sampled_runs], minlength=len(runs)).astype(float)
            weights = run_counts[run_s]
            total_weight = float(weights.sum())
            if total_weight <= 0:
                continue
            weighted_harm = weights * harm_s
            weighted_count = weights * count_s
            cum_weight = np.cumsum(weights)
            cum_harm = np.cumsum(weighted_harm)
            cum_count = np.cumsum(weighted_count)
            total_harm = float(cum_harm[-1])
            total_count = float(cum_count[-1])
            for coverage in coverages:
                threshold_pos = int(np.searchsorted(cum_weight, coverage * total_weight, side="left"))
                threshold_pos = min(max(threshold_pos, 0), len(risk_s) - 1)
                threshold = float(risk_s[threshold_pos])
                accepted_end = int(np.searchsorted(risk_s, threshold, side="right") - 1)
                accepted_weight = float(cum_weight[accepted_end])
                accepted_harm_sum = float(cum_harm[accepted_end])
                accepted_count_sum = float(cum_count[accepted_end])
                rejected_count_sum = float(total_count - accepted_count_sum)
                rejected_harm_sum = float(total_harm - accepted_harm_sum)
                accepted_harm_rate = accepted_harm_sum / accepted_weight if accepted_weight > 0 else np.nan
                rejected_harm_capture = rejected_count_sum / total_count if total_count > 0 else 0.0
                harmful_pulse_rejection = rejected_harm_sum / max(total_harm, 1.0)
                accepted_support = accepted_weight / total_weight
                got = {
                    "threshold": threshold,
                    "accepted_support": accepted_support,
                    "accepted_harm_rate": accepted_harm_rate,
                    "rejected_harm_capture": rejected_harm_capture,
                    "harmful_pulse_rejection": harmful_pulse_rejection,
                    "policy_loss": accepted_harm_rate + (1.0 - rejected_harm_capture),
                }
                for key, value in got.items():
                    values_by_coverage[coverage][key].append(value)
        for coverage in coverages:
            out = {"method": method["method"], "family": method["family"], "coverage": float(coverage)}
            for key, vals in values_by_coverage[coverage].items():
                out[key + "_ci95"] = ci(vals)
            rows.append(out)
    return pd.DataFrame(rows)


def threshold_stability(frontier: pd.DataFrame, by_run: pd.DataFrame, bootstrap: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for method in config["methods"]:
        part = frontier[frontier["method"] == method["method"]].copy()
        winners = []
        for coverage in config["benchmark"]["coverage_grid"]:
            cov = frontier[frontier["coverage"] == float(coverage)].sort_values("policy_loss").iloc[0]
            winners.append(str(cov["method"]))
        run_part = by_run[by_run["method"] == method["method"]]
        run_threshold_span = (
            run_part.groupby("coverage")["threshold"].max() - run_part.groupby("coverage")["threshold"].min()
        ).max()
        rows.append(
            {
                "method": method["method"],
                "family": method["family"],
                "threshold_min": float(part["threshold"].min()),
                "threshold_max": float(part["threshold"].max()),
                "threshold_range": float(part["threshold"].max() - part["threshold"].min()),
                "max_run_threshold_span": float(run_threshold_span),
                "winner_reversal_any_coverage": bool(len(set(winners)) > 1),
                "winner_sequence_by_coverage": " -> ".join(winners),
            }
        )
    return pd.DataFrame(rows)


def raw_support_tables(counts_by_run: pd.DataFrame, counts_by_group: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    group_rows = []
    stave_cols = ["B2", "B4", "B6", "B8"]
    for _, row in counts_by_group.iterrows():
        total = float(row["selected_pulses"])
        out = {
            "group": row["group"],
            "selected_pulses": int(row["selected_pulses"]),
            "events_with_selected": int(row["events_with_selected"]),
            "pulses_per_selected_event": float(row["selected_pulses"] / max(row["events_with_selected"], 1)),
        }
        for stave in stave_cols:
            out[stave + "_fraction"] = float(row[stave] / total) if total else np.nan
        group_rows.append(out)
    group_df = pd.DataFrame(group_rows)
    si = group_df[group_df["group"].eq("sample_i_analysis")].iloc[0]
    sii = group_df[group_df["group"].eq("sample_ii_analysis")].iloc[0]
    diff_rows = []
    for key in ["pulses_per_selected_event"] + [s + "_fraction" for s in stave_cols]:
        diff_rows.append(
            {
                "support_metric": key,
                "sample_i_analysis": float(si[key]),
                "sample_ii_analysis": float(sii[key]),
                "sample_ii_minus_sample_i": float(sii[key] - si[key]),
                "abs_delta": float(abs(sii[key] - si[key])),
            }
        )
    return group_df, pd.DataFrame(diff_rows)


def table_md(df: pd.DataFrame, floatfmt: str = ".4g", max_rows: int = 40) -> str:
    show = df.head(max_rows).copy()
    return show.to_markdown(index=False, floatfmt=floatfmt)


def write_report(
    output_dir: Path,
    config: dict,
    raw_match: pd.DataFrame,
    group_support: pd.DataFrame,
    support_delta: pd.DataFrame,
    frontier: pd.DataFrame,
    by_run: pd.DataFrame,
    bootstrap: pd.DataFrame,
    stability: pd.DataFrame,
    stave_frontier: pd.DataFrame,
    winner: dict,
    elapsed: float,
) -> None:
    primary_cov = float(config["benchmark"]["primary_coverage"])
    primary = frontier[frontier["coverage"].eq(primary_cov)].merge(bootstrap, on=["method", "family", "coverage"])
    primary = primary.sort_values("policy_loss")
    lines = []
    lines.append("# P12f Arbitration Threshold Frontier Under Sample-Family Drift\n")
    lines.append(f"- **Ticket:** `{config['ticket_id']}`")
    lines.append(f"- **Worker:** `{config['worker']}`")
    lines.append(f"- **Frozen P12e policy table:** `{config['p12e_predictions']}`")
    lines.append(f"- **Raw ROOT source:** `{config['raw_root_dir']}`")
    lines.append(f"- **Primary coverage:** `{primary_cov:.2f}` accepted support")
    lines.append(f"- **Run bootstrap:** `{config['benchmark']['bootstrap_reps']}` resamples of held-out Sample-II runs `{config['benchmark']['heldout_runs']}`")
    lines.append(f"- **Winner:** `{winner['method']}` with policy loss `{winner['policy_loss']:.4f}` and CI `{winner['policy_loss_ci95']}`\n")
    lines.append("## Scientific Question\n")
    lines.append(
        "This ticket tests whether the frozen P12e arbitration policy has a stable operating frontier, or whether the threshold that makes it look good is a family-specific operating point. "
        "The falsification criteria are: (i) changing the frozen acceptance coverage reverses the winning method; (ii) run-held-out confidence intervals show large threshold instability; or (iii) the raw Sample-I and Sample-II selected-pulse support constraints are so different that a single Sample-II threshold cannot plausibly be promoted without a Sample-I shadow-policy table.\n"
    )
    lines.append("## Raw ROOT Reproduction\n")
    lines.append(
        "The first gate reads `h101/HRDv` directly from the raw B-stack ROOT files, reshapes each event to eight channels by eighteen samples, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted maximum amplitude above 1000 ADC. The benchmark is interpreted only because this count gate passes exactly.\n"
    )
    lines.append(table_md(raw_match))
    lines.append("\n## Estimand and Equations\n")
    lines.append(
        "For method `m`, pulse `i`, risk score `s_{mi}`, and acceptance coverage `q`, the threshold is the empirical quantile\n\n"
        "`tau_m(q) = Q_q({s_{mi}: i in evaluation runs})`.\n\n"
        "The accepted set is `A_m(q) = {i: s_{mi} <= tau_m(q)}` and the rejected set is its complement. With binary harm `h_i` and harm count `c_i`, the frontier loss is\n\n"
        "`L_m(q) = mean_{i in A_m(q)} h_i + [1 - sum_{i notin A_m(q)} c_i / sum_i c_i]`.\n\n"
        "Lower is better: the first term penalizes harmful accepted pulses and the second penalizes failure to concentrate consumer harm in the rejected tail. All confidence intervals resample complete held-out runs with replacement and recompute `tau_m(q)` inside each bootstrap draw.\n"
    )
    lines.append("## Benchmark Panel\n")
    lines.append(
        "The panel is the frozen P12e policy table: a strong traditional atom-action risk rule, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new atom-prior residual CNN architecture. These are not refit in this ticket; the new contribution is the threshold-frontier and family-support audit of the frozen scores.\n"
    )
    lines.append("## Primary 90% Coverage Results\n")
    show_cols = [
        "method",
        "family",
        "threshold",
        "accepted_support",
        "accepted_harm_rate",
        "rejected_harm_capture",
        "policy_loss",
        "policy_loss_ci95",
    ]
    lines.append(table_md(primary[show_cols]))
    lines.append("\n## Coverage Frontier\n")
    lines.append(table_md(frontier[["method", "family", "coverage", "threshold", "accepted_harm_rate", "rejected_harm_capture", "policy_loss"]], max_rows=80))
    lines.append("\n## Per-Run Split Diagnostics\n")
    lines.append(
        "The table below shows the per-run scores at the primary coverage. The bootstrap intervals above are based on these complete run blocks rather than treating pulses as iid.\n"
    )
    lines.append(table_md(by_run[by_run["coverage"].eq(primary_cov)][["run", "method", "coverage", "threshold", "accepted_harm_rate", "rejected_harm_capture", "policy_loss"]], max_rows=80))
    lines.append("\n## Threshold Stability and Falsification\n")
    lines.append(table_md(stability))
    reversal = bool(stability["winner_reversal_any_coverage"].any())
    lines.append(
        "\nA winner reversal across the requested coverage grid is `{}`. The sequence field records the global winner at each coverage in grid order, so repeated identical entries support a stable frontier while method changes flag threshold tuning sensitivity.\n".format(
            str(reversal).lower()
        )
    )
    lines.append("## Raw Sample-Family Support Constraints\n")
    lines.append(table_md(group_support))
    lines.append("\n### Sample-I versus Sample-II Support Delta\n")
    lines.append(table_md(support_delta))
    lines.append(
        "\nThe frozen P12e table available in this repository contains only `sample_ii_analysis` policy rows. Therefore this ticket cannot honestly score Sample-I policy loss at row level. The raw ROOT support audit above is the detector-level family-drift constraint: Sample-I is much more B2-dominated than Sample-II, so a true promotion of a frozen threshold requires a P12e-compatible Sample-I shadow-policy table. This is a caveat, not a hidden correction.\n"
    )
    lines.append("## Accepted-Stave Composition\n")
    lines.append(table_md(stave_frontier[stave_frontier["coverage"].eq(primary_cov)], max_rows=80))
    lines.append("\n## Systematics and Caveats\n")
    lines.append("- The policy table is frozen and Sample-II-only; neural and tree methods are benchmarked as frozen P12e predictions rather than retrained in this ticket.")
    lines.append("- Run-bootstrap intervals have only seven held-out run units, so they reflect run-to-run instability but remain coarse.")
    lines.append("- The composite loss is an operational arbitration loss. Component harms span timing, charge, saturation, pile-up, baseline, dropout, PID, and energy proxies; it should not be read as a single detector-truth observable.")
    lines.append("- Thresholds are recalculated inside each bootstrap draw. This measures frontier stability, not fixed-threshold deployment variance.")
    lines.append("- Raw Sample-I/Sample-II support deltas are directly reproduced from ROOT; Sample-I row-level policy loss is intentionally not imputed.\n")
    lines.append("## Conclusion\n")
    lines.append(
        f"At the primary 90% accepted-support operating point the winner is `{winner['method']}`. "
        f"Its policy loss is `{winner['policy_loss']:.4f}` with 95% run-bootstrap CI `{winner['policy_loss_ci95']}`. "
        f"The coverage-grid winner reversal flag is `{str(reversal).lower()}`. Because the available frozen P12e table is Sample-II-only, the family-drift conclusion is conditional: the Sample-II frontier is measured, raw Sample-I/Sample-II support drift is reproduced, and a row-level Sample-I shadow policy is required before claiming a stable cross-family deployment threshold.\n"
    )
    lines.append("## Reproducibility\n")
    lines.append("```bash")
    lines.append("/home/billy/anaconda3/bin/python scripts/p12f_1783652352_27274_78d76ca4_arbitration_threshold_frontier.py --config configs/p12f_1783652352_27274_78d76ca4_arbitration_threshold_frontier.json")
    lines.append("```")
    lines.append(f"\nRuntime: {elapsed:.1f} s.")
    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def input_manifest(config: dict, script_path: Path, config_path: Path) -> pd.DataFrame:
    rows = []
    for run in p12a.configured_runs(config):
        path = p12a.raw_file(config, run)
        rows.append({"kind": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    for path in [Path(config["p12e_predictions"]), script_path, config_path, Path("scripts/p12a_1781023340_632_43377364_pulse_axis_covariance.py")]:
        rows.append({"kind": "code_config_or_artifact", "path": str(path), "sha256": sha256_file(path)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    _, counts_by_run, counts_by_group = p12a.scan_raw(config)
    raw_match = p12a.compare_counts(config, counts_by_group)
    raw_match.to_csv(output_dir / "raw_count_match.csv", index=False)
    counts_by_run.to_csv(output_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(output_dir / "counts_by_group.csv", index=False)
    if not bool(raw_match["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed")

    policy = prepare_policy_frame(config)
    policy.to_csv(output_dir / "p12e_policy_rows_audit.csv.gz", index=False)
    frontier, by_run, stave_frontier = method_frontier(policy, config)
    bootstrap = run_bootstrap(policy, config)
    stability = threshold_stability(frontier, by_run, bootstrap, config)
    group_support, support_delta = raw_support_tables(counts_by_run, counts_by_group)

    primary_cov = float(config["benchmark"]["primary_coverage"])
    primary = frontier[frontier["coverage"].eq(primary_cov)].merge(bootstrap, on=["method", "family", "coverage"])
    winner = primary.sort_values(["policy_loss", "accepted_harm_rate", "rejected_harm_capture"], ascending=[True, True, False]).iloc[0].to_dict()

    frontier.to_csv(output_dir / "threshold_frontier.csv", index=False)
    by_run.to_csv(output_dir / "threshold_frontier_by_run.csv", index=False)
    bootstrap.to_csv(output_dir / "threshold_frontier_bootstrap.csv", index=False)
    stability.to_csv(output_dir / "threshold_stability.csv", index=False)
    stave_frontier.to_csv(output_dir / "accepted_stave_frontier.csv", index=False)
    group_support.to_csv(output_dir / "raw_family_support.csv", index=False)
    support_delta.to_csv(output_dir / "raw_family_support_delta.csv", index=False)
    input_manifest(config, Path(__file__), args.config).to_csv(output_dir / "input_sha256.csv", index=False)

    elapsed = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(raw_match["pass"].all()),
        "raw_reproduction": {
            "source": config["raw_root_dir"],
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced_selected_pulses": int(raw_match.iloc[0]["reproduced"]),
            "delta": int(raw_match.iloc[0]["delta"]),
            "pass": bool(raw_match["pass"].all()),
        },
        "split": {
            "evaluation_policy_rows": "frozen P12e held-out sample_ii_analysis rows",
            "heldout_runs": [int(x) for x in config["benchmark"]["heldout_runs"]],
            "bootstrap_unit": "run block",
            "bootstrap_reps": int(config["benchmark"]["bootstrap_reps"]),
            "coverage_grid": [float(x) for x in config["benchmark"]["coverage_grid"]],
            "primary_coverage": primary_cov,
        },
        "methods_benchmarked": [m["method"] for m in config["methods"]],
        "primary_metric": "policy_loss = accepted harm rate + (1 - rejected harm-count capture), lower is better",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "coverage": float(winner["coverage"]),
            "threshold": float(winner["threshold"]),
            "policy_loss": float(winner["policy_loss"]),
            "policy_loss_ci95": winner["policy_loss_ci95"],
            "accepted_harm_rate": float(winner["accepted_harm_rate"]),
            "accepted_harm_rate_ci95": winner["accepted_harm_rate_ci95"],
            "rejected_harm_capture": float(winner["rejected_harm_capture"]),
            "rejected_harm_capture_ci95": winner["rejected_harm_capture_ci95"],
            "accepted_support": float(winner["accepted_support"]),
        },
        "winner_reversal_any_coverage": bool(stability["winner_reversal_any_coverage"].any()),
        "raw_family_support_delta_max_abs": float(support_delta["abs_delta"].max()),
        "sample_i_policy_rows_available": bool((policy["group"] == "sample_i_analysis").any()),
        "sample_family_caveat": "Frozen P12e policy rows are Sample-II only; Sample-I is audited through raw ROOT support, not imputed policy loss.",
        "next_ticket": config["next_ticket"],
        "runtime_seconds": elapsed,
        "artifacts": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "raw_count_match.csv",
            "counts_by_run.csv",
            "counts_by_group.csv",
            "threshold_frontier.csv",
            "threshold_frontier_by_run.csv",
            "threshold_frontier_bootstrap.csv",
            "threshold_stability.csv",
            "accepted_stave_frontier.csv",
            "raw_family_support.csv",
            "raw_family_support_delta.csv",
            "p12e_policy_rows_audit.csv.gz",
            "input_sha256.csv",
        ],
    }
    (output_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(
        output_dir,
        config,
        raw_match,
        group_support,
        support_delta,
        frontier,
        by_run,
        bootstrap,
        stability,
        stave_frontier,
        result["winner"],
        elapsed,
    )
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "script": str(Path(__file__)),
        "config": str(args.config),
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), args.config),
        "git_commit": git_commit(),
        "created_unix": time.time(),
        "python": sys.version,
        "platform": platform.platform(),
        "artifacts": [{"path": str(output_dir / name)} for name in result["artifacts"]],
    }
    (output_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")
    print("wrote {}".format(output_dir))
    print("winner {}".format(result["winner"]["method"]))


if __name__ == "__main__":
    main()
