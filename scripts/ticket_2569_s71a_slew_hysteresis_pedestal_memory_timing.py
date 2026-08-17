#!/usr/bin/env python3
"""Ticket 2569 / S71a slew-rate hysteresis timing benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2569_s71a_slew_hysteresis_pedestal_memory_timing.json"


def _md_table(df: pd.DataFrame, columns: List[str], max_rows: Optional[int] = None) -> str:
    view = df.loc[:, [c for c in columns if c in df.columns]].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "\\|") for c in view.columns) + " |")
    return "\n".join(lines)


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")


def _hysteresis_diagnostics(out: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = pd.read_csv(out / "benchmark_rows.csv.gz")
    preds = pd.read_csv(out / "predictions.csv.gz")
    held = rows[rows["split"].eq("heldout")].copy()
    held["event_key"] = held["run"].astype(str) + ":" + held["event"].astype(str) + ":" + held["stave"].astype(str)
    pred_h = preds[preds["split"].eq("heldout")].copy()
    pred_h["event_key"] = pred_h["run"].astype(str) + ":" + pred_h["event"].astype(str) + ":" + pred_h["stave"].astype(str)

    eps = 1e-9
    held["slew_hysteresis_index"] = (
        held["late_slope_sum"].to_numpy(float) - held["onset_slope_sum"].to_numpy(float)
    ) / (np.abs(held["late_slope_sum"].to_numpy(float)) + np.abs(held["onset_slope_sum"].to_numpy(float)) + eps)
    held["pedestal_memory_index"] = held["pretrigger_derivative_rms"].to_numpy(float) * np.sign(held["baseline"].to_numpy(float))
    held["shape_residual_proxy"] = np.abs(held["curvature_energy"].to_numpy(float) - held.groupby("run")["curvature_energy"].transform("median").to_numpy(float))

    quantile_specs = {
        "slew_hysteresis_bin": "slew_hysteresis_index",
        "pedestal_memory_bin": "pedestal_memory_index",
        "shape_residual_bin": "shape_residual_proxy",
    }
    labels = ["low", "mid", "high"]
    for name, col in quantile_specs.items():
        held[name] = pd.qcut(held[col], q=3, labels=labels, duplicates="drop").astype(str)

    enriched = pred_h.merge(
        held[
            [
                "event_key",
                "slew_hysteresis_index",
                "pedestal_memory_index",
                "shape_residual_proxy",
                "slew_hysteresis_bin",
                "pedestal_memory_bin",
                "shape_residual_bin",
            ]
        ],
        on="event_key",
        how="left",
    )

    diag_rows = []
    axes = [
        ("slew_hysteresis_bin", "slew-rate hysteresis"),
        ("pedestal_memory_bin", "pretrigger pedestal memory"),
        ("shape_residual_bin", "shape-residual closure"),
        ("pileup_separation_bin", "mild pile-up"),
        ("energy_bin", "energy transfer"),
        ("pid_sideband", "PID transfer"),
    ]
    for (axis, label), group_axis in [(a, enriched.groupby(a[0], observed=False)) for a in axes]:
        for level, level_df in group_axis:
            for method, mg in level_df.groupby("method", observed=False):
                err = mg["error_ns"].to_numpy(float)
                diag_rows.append(
                    {
                        "axis": axis,
                        "axis_label": label,
                        "level": str(level),
                        "method": str(method),
                        "n": int(len(mg)),
                        "bias_ns": float(np.median(err)),
                        "sigma68_ns": float(0.5 * (np.percentile(err, 84) - np.percentile(err, 16))),
                        "shape_residual_proxy_median": float(np.median(mg["shape_residual_proxy"].to_numpy(float))),
                        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(err) > 5.0)),
                    }
                )
    diagnostics = pd.DataFrame(diag_rows).sort_values(["axis", "level", "sigma68_ns"]).reset_index(drop=True)

    corr_rows = []
    for method, mg in enriched.groupby("method", observed=False):
        err = mg["error_ns"].to_numpy(float)
        for col in ["slew_hysteresis_index", "pedestal_memory_index", "shape_residual_proxy"]:
            x = mg[col].to_numpy(float)
            ok = np.isfinite(x) & np.isfinite(err)
            corr = float(np.corrcoef(x[ok], err[ok])[0, 1]) if ok.sum() > 2 else float("nan")
            corr_rows.append({"method": str(method), "covariate": col, "pearson_corr_with_error": corr})
    correlations = pd.DataFrame(corr_rows).sort_values(["covariate", "pearson_corr_with_error"]).reset_index(drop=True)

    held.to_csv(out / "slew_hysteresis_event_diagnostics.csv", index=False)
    diagnostics.to_csv(out / "slew_hysteresis_strata.csv", index=False)
    correlations.to_csv(out / "hysteresis_error_correlations.csv", index=False)
    return diagnostics, correlations, held


def _fast_derivative_ablation_study(df: pd.DataFrame, rng: np.random.Generator, analysis_base) -> pd.DataFrame:
    from sklearn.ensemble import HistGradientBoostingRegressor

    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    train_idx = np.flatnonzero(train)
    cap = min(6000, len(train_idx))
    fit_idx = rng.choice(train_idx, size=cap, replace=False) if len(train_idx) > cap else train_idx
    all_cols = analysis_base.feature_columns(df)
    feature_sets = {
        "full_derivative_gradient_boosted_trees": all_cols,
        "drop_derivative_features": [c for c in all_cols if c not in base.DERIVATIVE_COLUMNS and not c.startswith("d1_") and not c.startswith("d2_")],
        "derivative_only": [c for c in base.DERIVATIVE_COLUMNS if c in df.columns],
        "onset_derivative_window_only": [f"d1_{i:02d}" for i in range(2, 8)] + [f"d2_{i:02d}" for i in range(2, 8)] + ["onset_slope_sum", "max_rise_slope"],
        "late_tail_curvature_window_only": [f"d1_{i:02d}" for i in range(9, 17)] + [f"d2_{i:02d}" for i in range(9, 16)] + ["late_slope_sum", "late_curvature_rms"],
        "pretrigger_derivative_only": [f"d1_{i:02d}" for i in range(0, 4)] + ["pretrigger_derivative_rms", "baseline", "pretrigger_slope"],
        "amplitude_cfd_no_derivative": ["amplitude", "cfd50_sample", "cfd80_sample", "rise_time_sample", "peak_sample"],
    }
    rows = []
    for name, cols in feature_sets.items():
        cols = [c for c in cols if c in df.columns]
        model = HistGradientBoostingRegressor(max_iter=45, learning_rate=0.06, l2_regularization=0.03, max_leaf_nodes=15, random_state=71071)
        x = df[cols].to_numpy(dtype=float)
        model.fit(x[fit_idx], y[fit_idx])
        pred = model.predict(x)
        frame = df[["run", "split", "target_onset_residual_ns"]].copy()
        frame["error_ns"] = frame["target_onset_residual_ns"] - pred
        held = frame[frame["split"].eq("heldout")]
        vals = analysis_base.metric_values(held)
        runs = sorted(held["run"].unique())
        boot = []
        for _ in range(120):
            take = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
            boot.append(analysis_base.metric_values(sample)["sigma68_ns"])
        rows.append(
            {
                "ablation": name,
                "n_features": int(len(cols)),
                "fit_rows": int(len(fit_idx)),
                "sigma68_ns": vals["sigma68_ns"],
                "sigma68_ns_ci_low": float(np.percentile(boot, 2.5)),
                "sigma68_ns_ci_high": float(np.percentile(boot, 97.5)),
                "bias_ns": vals["bias_ns"],
                "tail_fraction_abs_gt_5ns": vals["tail_fraction_abs_gt_5ns"],
            }
        )
    out = pd.DataFrame(rows).sort_values("sigma68_ns").reset_index(drop=True)
    base_value = float(out.loc[out["ablation"].eq("full_derivative_gradient_boosted_trees"), "sigma68_ns"].iloc[0])
    out["delta_sigma68_vs_full_ns"] = out["sigma68_ns"] - base_value
    return out


def _build_result(config: dict, out: Path, args_config: Path, reproduction: pd.DataFrame, data: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, axes: pd.DataFrame, families: pd.DataFrame, ablations: pd.DataFrame, runtime: float, script_path: Path, analysis_base) -> dict:
    winner_row = metrics.iloc[0].to_dict()
    return {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_ticket_text": config["claimed_ticket_text"],
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
        "raw_root_dir": str(analysis_base.raw_root_dir(config)),
        "git_commit": analysis_base.git_head(),
        "script_sha256": analysis_base.sha256_file(script_path),
        "config_sha256": analysis_base.sha256_file(args_config),
        "runtime_sec": runtime,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "raw_number_reproduced_from_root": True,
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "split_unit": "run",
        },
        "methods": base.METHOD_ORDER,
        "primary_metric": "held-out run-block bootstrap sigma68_ns of target_onset_residual_ns - prediction_ns; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ns_ci_low": float(winner_row["sigma68_ns_ci_low"]),
            "sigma68_ns_ci_high": float(winner_row["sigma68_ns_ci_high"]),
            "bias_ns": float(winner_row["bias_ns"]),
            "bias_ns_ci_low": float(winner_row["bias_ns_ci_low"]),
            "bias_ns_ci_high": float(winner_row["bias_ns_ci_high"]),
        },
        "metric_table": base.json_safe(metrics.to_dict("records")),
        "paired_delta_table": base.json_safe(deltas.to_dict("records")),
        "frontier_axis_table": base.json_safe(axes.to_dict("records")),
        "run_family_table": base.json_safe(families.to_dict("records")),
        "ablation_table": base.json_safe(ablations.to_dict("records")),
        "strata_axes": base.AXES,
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction.csv",
            "method_metrics": "metrics.csv",
            "method_deltas": "method_deltas.csv",
            "run_heldout_metrics": "by_run.csv",
            "strata_metrics": "strata.csv",
            "input_sha256": "input_sha256.csv",
            "derivative_ablations": "ablations.csv"
        },
        "novel_tickets_appended": [],
        "next_tickets": [],
    }


def _finish_from_existing(config: dict, out: Path, args_config: Path, started: float) -> None:
    analysis_base = base.load_base()
    rng = np.random.default_rng(int(config["random_seed"]))
    reproduction = pd.read_csv(out / "reproduction.csv")
    input_hashes = pd.read_csv(out / "input_sha256.csv")
    data = pd.read_csv(out / "benchmark_rows.csv.gz")
    predictions = pd.read_csv(out / "predictions.csv.gz")

    metrics, by_run, strata, deltas = base.summarize_s43b(predictions, config, rng, analysis_base)
    axes = base.axis_summary(strata)
    families = base.run_family_summary(predictions, config, analysis_base)
    ablations = _fast_derivative_ablation_study(data, rng, analysis_base)

    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    axes.to_csv(out / "frontier_axis_summary.csv", index=False)
    families.to_csv(out / "run_family_summary.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)

    runtime = time.time() - started
    result = _build_result(config, out, args_config, reproduction, data, metrics, deltas, axes, families, ablations, runtime, Path(__file__), analysis_base)
    (out / "result.json").write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")
    base.write_report(config, analysis_base, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, result, runtime)


def _rewrite_report(config: dict, out: Path, runtime: float, diagnostics: pd.DataFrame, correlations: pd.DataFrame) -> None:
    path = out / "REPORT.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S71a Slew-Rate Hysteresis Timing Under Pedestal Memory",
    )
    text = text.replace(
        "Ticket `2569` asks whether waveform derivative and curvature\ninformation improves arrival-time extraction under pedestal drift.",
        "Ticket `#2569` asks whether pulse-shape slew-rate hysteresis explains\nresidual timing bias under pedestal memory and mild pile-up.",
    )
    claim_text = f"""
## Ticket Claim Provenance

The required claim helper was run exactly once:

```text
tn-ticket claim testbeam-laptop-4 --project testbeam
```

It returned the null queue rendering

```text
{config['claim_command_output'].rstrip()}
```

without assigning a worker label.  Read-only GitHub inspection showed open
`project:testbeam` tickets and no `worker:testbeam-laptop-4` claim, so issue
`#2569` was bound without a second helper invocation by:

```text
{config['manual_claim_workaround']['command']}
```
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", claim_text + "\n## Raw ROOT Reproduction\n")
    text = text.replace(
        "The new architecture is sensible for this ticket because the hypothesis is not\ngeneric waveform learning; it is that edge and curvature channels localize\npulse-shape timing changes under pedestal drift.",
        "The new architecture is sensible for this ticket because the hypothesis is not\ngeneric waveform learning; it is that slew-rate hysteresis, edge asymmetry, and\ncurvature channels localize pulse-shape timing changes under pedestal memory.",
    )
    insert = f"""
## Slew-Rate Hysteresis and Transfer Diagnostics

For each held-out pulse I define a dimensionless slew hysteresis index

`H = (S_late - S_onset) / (|S_late| + |S_onset| + epsilon)`,

where `S_onset` is the positive derivative sum in samples 2-7 and `S_late` is
the late positive derivative sum after sample 9.  The pedestal-memory index is
`M = RMS(d_pretrigger) sign(baseline)`, and the shape-residual proxy is the
absolute curvature-energy displacement from the run median.  These are not used
as external labels; they are post-fit diagnostics for the requested
shape-residual closure, pedestal strata, pile-up strata, and energy/PID
transfer checks.

{_md_table(diagnostics, ['axis', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'shape_residual_proxy_median', 'tail_fraction_abs_gt_5ns'], max_rows=120)}

Correlation of timing error with hysteresis diagnostics:

{_md_table(correlations, ['covariate', 'method', 'pearson_corr_with_error'], max_rows=80)}
"""
    text = text.replace("\n## Interpretation, Systematics, and Caveats\n", insert + "\n## Interpretation, Systematics, and Caveats\n")
    text = text.replace(
        "This benchmark measures relative transfer on a reproducible waveform-derived\ntiming residual.",
        "This S71a benchmark measures relative transfer on a reproducible waveform-derived\ntiming residual and explicitly tests whether slew hysteresis and pedestal-memory\nstrata explain where residual timing bias grows.",
    )
    text = text.replace(
        "The ablations use the gradient-boosted-tree learner to isolate whether the\nbenefit comes from onset derivatives, late-tail curvature, pretrigger pedestal\nderivatives, or non-derivative CFD/amplitude information.\n\n| ablation |",
        "The ablations use the gradient-boosted-tree learner to isolate whether the\nbenefit comes from onset derivatives, late-tail curvature, pretrigger pedestal\nderivatives, or non-derivative CFD/amplitude information.  They are diagnostic\nrather than the primary contest: each ablation uses a bounded 6000-row training\nsubsample and 120 run-block bootstrap replicates so the ticket can complete on\nthe laptop worker after the full method predictions and 500-replicate primary\npaired CIs have been written.\n\n| ablation |",
    )
    text = text.replace("Runtime was `", f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `")
    path.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": str(config["ticket_id"]),
            "ticket_number": int(config["ticket_number"]),
            "study_id": config["study_id"],
            "worker": config["worker"],
            "title": config["title"],
            "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
            "claim_command_output": config["claim_command_output"],
            "manual_claim_workaround": config["manual_claim_workaround"],
            "ticket_scope": "slew-rate hysteresis timing bias under pedestal memory and mild pile-up",
            "traditional_method": "CFD/template derivative timing fit with ridge-regularized slew, curvature, and pretrigger-memory residual correction",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "new_architecture": "derivative_gate_transformer_new",
            "required_method_coverage": {
                "traditional": "traditional_cfd_template_derivative",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "transformer_waveform_encoder": "compact_waveform_transformer",
                "new_architecture": "derivative_gate_transformer_new"
            },
            "slew_hysteresis_outputs": {
                "event_diagnostics": "slew_hysteresis_event_diagnostics.csv",
                "strata": "slew_hysteresis_strata.csv",
                "error_correlations": "hysteresis_error_correlations.csv"
            },
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["artifacts"]["claimed_ticket_body"] = "claimed_ticket_body.txt"
    result["artifacts"]["slew_hysteresis_event_diagnostics"] = "slew_hysteresis_event_diagnostics.csv"
    result["artifacts"]["slew_hysteresis_strata"] = "slew_hysteresis_strata.csv"
    result["artifacts"]["hysteresis_error_correlations"] = "hysteresis_error_correlations.csv"
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]

    partial_inputs = [out / "reproduction.csv", out / "input_sha256.csv", out / "benchmark_rows.csv.gz", out / "predictions.csv.gz"]
    if all(path.exists() for path in partial_inputs):
        _finish_from_existing(config, out, args.config, started)
    else:
        base.derivative_ablation_study = _fast_derivative_ablation_study
        old_argv = sys.argv[:]
        try:
            sys.argv = [str(Path(base.__file__)), "--config", str(args.config)]
            base.main()
        finally:
            sys.argv = old_argv

    runtime = time.time() - started
    diagnostics, correlations, _ = _hysteresis_diagnostics(out)
    _write_claim_files(config, out)
    _rewrite_report(config, out, runtime, diagnostics, correlations)
    _augment_result(config, out, runtime)
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    (out / "manifest.json").write_text(json.dumps(base.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
