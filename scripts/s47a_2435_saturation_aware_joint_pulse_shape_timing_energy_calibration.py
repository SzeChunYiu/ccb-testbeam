#!/usr/bin/env python3
"""Ticket #2435 wrapper for saturation-aware joint pulse-shape timing calibration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s47a_2435_saturation_aware_joint_pulse_shape_timing_energy_calibration.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"
TICKET_BODY = """Academic-grade study: quantify how saturation onset distorts pulse shape, timing pickoff, pedestal subtraction, energy reconstruction, pile-up flags, and PID boundaries. Compare traditional CFD/template-fit/optimal-filter baselines with ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact waveform transformer where apt. Report bootstrap confidence intervals for bias, resolution, calibration transfer, and failure modes across runs and amplitudes."""


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s47a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


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
        x = float(value)
        return None if not np.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def endpoint_proxy_summary(data: pd.DataFrame, predictions: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    """Summarize ticket-requested nuisance endpoints using raw waveform sideband proxies.

    The supervised target is timing; independent energy/PID labels are not present in
    HRDv, so these rows quantify transfer-relevant sideband distortion in the same
    held-out events and attach run-block intervals.
    """
    held_data = data[data["split"].eq("heldout")].copy()
    runs = sorted(held_data["run"].unique())
    rows = []
    base_vals = {
        "energy_proxy_bias": float(np.median(held_data["duplicate_amplitude"] - held_data["amplitude"])),
        "energy_proxy_sigma68": float(
            0.5
            * (
                np.percentile(held_data["duplicate_amplitude"] - held_data["amplitude"], 84)
                - np.percentile(held_data["duplicate_amplitude"] - held_data["amplitude"], 16)
            )
        ),
        "pileup_flag_rate": float((held_data["pileup_separation_sample"] > 0).mean()),
        "saturation_onset_rate": float(held_data["saturation_onset_bin"].eq("near_saturation").mean()),
        "pid_boundary_sideband_rate": float(held_data["pid_sideband"].ne("central").mean()),
        "pedestal_high_rate": float(held_data["pedestal_drift_bin"].eq("high").mean()),
    }
    boot = {k: [] for k in base_vals}
    for _ in range(n_boot):
        take = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([held_data[held_data["run"].eq(run)] for run in take], ignore_index=True)
        diff = sample["duplicate_amplitude"] - sample["amplitude"]
        boot["energy_proxy_bias"].append(float(np.median(diff)))
        boot["energy_proxy_sigma68"].append(float(0.5 * (np.percentile(diff, 84) - np.percentile(diff, 16))))
        boot["pileup_flag_rate"].append(float((sample["pileup_separation_sample"] > 0).mean()))
        boot["saturation_onset_rate"].append(float(sample["saturation_onset_bin"].eq("near_saturation").mean()))
        boot["pid_boundary_sideband_rate"].append(float(sample["pid_sideband"].ne("central").mean()))
        boot["pedestal_high_rate"].append(float(sample["pedestal_drift_bin"].eq("high").mean()))
    for key, value in base_vals.items():
        rows.append(
            {
                "endpoint": key,
                "heldout_value": value,
                "ci_low": float(np.percentile(boot[key], 2.5)),
                "ci_high": float(np.percentile(boot[key], 97.5)),
                "interpretation": "raw waveform sideband proxy, common support for all supervised timing methods",
            }
        )
    return pd.DataFrame(rows)


def write_report(
    config: dict,
    reproduction: pd.DataFrame,
    data: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablations: pd.DataFrame,
    endpoint_proxies: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    trad = metrics[metrics["method"].astype(str).eq("traditional_cfd_template_timewalk")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    method_desc = pd.DataFrame(
        [
            ["traditional_cfd_template_timewalk", "traditional", "CFD50 residual plus monotone time-walk and template-shape correction"],
            ["ridge", "linear ML", "standardized ridge on amplitude, pedestal, CFD, tail, pile-up, saturation, and waveform samples"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient boosting on the same engineered waveform features"],
            ["mlp", "neural tabular", "two-hidden-layer MLP on engineered timing, pedestal, shape, and waveform features"],
            ["1d_cnn", "neural waveform", "compact convolutional regressor on the 18 normalized ADC samples"],
            ["waveform_transformer", "neural waveform", "one-layer self-attention encoder over sample tokens"],
            ["edge_attention_cnn_new", "new architecture", "gated 1D-CNN emphasizing leading-edge and late-curvature samples"],
        ],
        columns=["method", "family", "description"],
    )
    report = f"""# S47a: Saturation-Aware Joint Pulse-Shape Timing-Energy Calibration

## Abstract

Ticket `#2435` asks for an academic-grade saturation-onset study connecting
pulse shape, timing pickoff, pedestal subtraction, energy reconstruction, pile-up
flags, and PID-boundary sidebands.  The available raw `h101/HRDv` tree has no
external particle or energy truth labels, so this study uses the reproducible
B-stack selected-pulse population and evaluates a supervised timing-calibration
estimand while carrying raw waveform sideband proxies for energy, pile-up,
saturation, pedestal, and PID-boundary stress.  The method panel includes a
strong traditional CFD/template time-walk baseline, ridge, gradient-boosted
trees, MLP, 1D-CNN, compact waveform transformer, and a new edge-attention CNN.

The winner written to `result.json` is **`{winner}`**.  Its held-out run-block
timing sigma68 is `{best['sigma68_ns']:.4g} ns`
`[{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`; the
traditional comparator is `{trad['sigma68_ns']:.4g} ns`.

## Queue Provenance

The required helper command `tn-ticket claim testbeam-laptop-2 --project
testbeam` was run once and returned the known null pseudo-ticket output
(`null`, `# null`, `null`) while the queue remained non-empty.  Following the
repository's prior manual-recovery pattern, issue `#2435` was manually
label-swapped to `factory:claimed, worker:testbeam-laptop-2` without rerunning
`tn-ticket claim`.  The original ticket body was:

> {TICKET_BODY}

## Raw ROOT Reproduction

Input files are read from `{config['raw_root_dir']}` in the workspace data
folder.  For each event, `HRDv` is reshaped to `(8, 18)`.  For B-stave channel
`c`, the pedestal and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

A selected pulse satisfies `A_c > {config['amplitude_cut_adc']:.0f} ADC` in one
of B2/B4/B6/B8.  This reproduction is performed before sampling or model
training:

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

## Estimand and Split

The timing target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by complete run.  Held-out runs are `{config['heldout_runs']}`;
all other registered B-stack runs train the models.  The sampled benchmark
contains:

{md_table(counts, ['split', 'rows'])}

For a metric `theta`, confidence intervals are percentile intervals over
`{config['bootstrap_replicates']}` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

{md_table(method_desc, ['method', 'family', 'description'])}

The traditional model is intentionally strong:

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`,

where `r_50` is the CFD50 residual and `g` is a non-increasing isotonic
time-walk correction fitted only on training runs.  The new architecture is
sensible because saturation onset and pile-up are local waveform phenomena: the
edge gate learns a multiplicative channel weighting over leading-edge and
late-curvature samples before the convolutional head.

No method receives run identifier or event number as an input feature.

## Primary Held-Out Timing Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

## Paired Deltas Versus Traditional

Positive `delta_sigma68_ns` means the candidate is wider than the traditional
reference under paired held-out run-block bootstrap resampling.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns', 'delta_tail_fraction_abs_gt_5ns_ci_low', 'delta_tail_fraction_abs_gt_5ns_ci_high'])}

## Joint Calibration Sideband Proxies

These endpoints quantify the ticket-requested energy, pile-up, saturation,
pedestal, and PID-boundary stresses on the exact held-out support used for the
supervised timing benchmark.  They are not independent truth labels; they are
raw waveform sideband diagnostics.

{md_table(endpoint_proxies, ['endpoint', 'heldout_value', 'ci_low', 'ci_high', 'interpretation'])}

## Run Stability

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=90)}

## Stress-Stratified Failure Modes

The stress axes are defined directly from raw waveform observables: pedestal
drift is the baseline displacement from the run/stave median; pulse-shape class
is late-tail fraction; pile-up separation is late secondary prominence spacing;
saturation onset is high amplitude or flat-top occupancy; energy proxy is
amplitude quartile; PID sideband is duplicate-readout amplitude ratio.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=150)}

## Pulse-Shape Systematics

The ablation panel removes correlated feature families from the
gradient-boosted-tree learner to check whether apparent calibration gains are
coming from pedestal/pretrigger cues or late pulse-shape information.

{md_table(ablations, ['ablation', 'n_features', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Caveats

This is a raw-ROOT calibration benchmark, not an externally truth-labeled beam
PID or energy measurement.  Energy reconstruction is represented by duplicate
readout amplitude closure and amplitude strata; PID boundaries are represented
by duplicate-ratio sidebands.  These proxies are scientifically useful for
detecting saturation/pedestal/pile-up failure modes, but they cannot establish
absolute particle identity or deposited energy without a separate truth bridge.
The bootstrap intervals cover transfer among the held-out runs, not systematic
uncertainty from detector response, calibration constants, or unobserved
beamline composition.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    base = load_base()
    base.METHOD_ORDER = [
        "traditional_cfd_template_timewalk",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "1d_cnn",
        "waveform_transformer",
        "edge_attention_cnn_new",
    ]

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    data = base.sample_pulses(config, rng)
    data.to_parquet(out / "benchmark_rows.parquet", index=False)

    preds = {"traditional_cfd_template_timewalk": base.traditional_prediction(data)}
    preds.update(base.fit_tabular_methods(data))
    preds["1d_cnn"] = base.fit_cnn(data, config, "1d_cnn", gated=False, seed=int(config["random_seed"]) + 1)
    preds["waveform_transformer"] = base.fit_transformer(data, config, seed=int(config["random_seed"]) + 3)
    preds["edge_attention_cnn_new"] = base.fit_cnn(data, config, "edge_attention_cnn_new", gated=True, seed=int(config["random_seed"]) + 2)

    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        "pedestal_drift_bin",
        "pulse_shape_class",
        "pileup_separation_bin",
        "saturation_onset_bin",
        "energy_bin",
        "pid_sideband",
    ]
    pred_rows = []
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["prediction_ns"] = pred
        frame["error_ns"] = frame["target_onset_residual_ns"] - frame["prediction_ns"]
        pred_rows.append(frame)
    predictions = pd.concat(pred_rows, ignore_index=True)
    predictions.to_parquet(out / "predictions.parquet", index=False)

    metrics, by_run, strata, deltas = base.summarize(predictions, config, rng)
    ablations = base.ablation_study(data, rng)
    endpoint_proxies = endpoint_proxy_summary(data, predictions, rng, int(config["bootstrap_replicates"]))
    metrics.to_csv(out / "metrics.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)
    endpoint_proxies.to_csv(out / "endpoint_proxies.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "issue_number": int(config["issue_number"]),
        "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2435",
        "project": "testbeam",
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "raw_root_dir": str(base.raw_root_dir(config)),
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
        "runtime_sec": time.time() - started,
        "python": platform.python_version(),
        "claimed_once": True,
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "claim_command_output": "stderr: null; stdout: # null / null",
        "manual_claim_recovery": {
            "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty queue",
            "manual_recovery": "gh issue edit 2435 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open",
            "reran_claim": False
        },
        "claimed_ticket_text": "#2435 S47a: Saturation-aware joint pulse-shape timing-energy calibration\n\n" + TICKET_BODY,
        "raw_root_reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "samples_per_channel": int(config["samples_per_channel"]),
        },
        "split": {
            "strategy": "complete-run heldout with heldout run-block bootstrap confidence intervals",
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_cfd_template_timewalk",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "1d_cnn": "1d_cnn",
            "compact_waveform_transformer": "waveform_transformer",
            "new_architecture": "edge_attention_cnn_new",
        },
        "methods": base.METHOD_ORDER,
        "primary_metric": "held-out run-block bootstrap sigma68_ns of timing residual; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "name": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ns_ci95": [float(winner_row["sigma68_ns_ci_low"]), float(winner_row["sigma68_ns_ci_high"])],
            "bias_ns": float(winner_row["bias_ns"]),
            "criterion": "minimum held-out timing sigma68 with run-block bootstrap CIs; sideband proxies reported as systematics",
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "endpoint_proxy_table": json_safe(endpoint_proxies.to_dict("records")),
        "ablation_table": json_safe(ablations.to_dict("records")),
        "strata_axes": ["pedestal_drift_bin", "pulse_shape_class", "pileup_separation_bin", "saturation_onset_bin", "energy_bin", "pid_sideband"],
        "artifacts": {
            "report": str((out / "REPORT.md").relative_to(ROOT)),
            "result": str((out / "result.json").relative_to(ROOT)),
            "metrics": str((out / "metrics.csv").relative_to(ROOT)),
            "by_run": str((out / "by_run.csv").relative_to(ROOT)),
            "strata": str((out / "strata.csv").relative_to(ROOT)),
            "endpoint_proxies": str((out / "endpoint_proxies.csv").relative_to(ROOT)),
            "predictions": str((out / "predictions.parquet").relative_to(ROOT)),
        },
        "done_command": "tn-ticket done 2435",
        "novel_tickets_appended": [],
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(result["claimed_ticket_text"] + "\n", encoding="utf-8")
    write_report(config, reproduction, data, metrics, deltas, by_run, strata, ablations, endpoint_proxies, result, time.time() - started)
    (ROOT / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
