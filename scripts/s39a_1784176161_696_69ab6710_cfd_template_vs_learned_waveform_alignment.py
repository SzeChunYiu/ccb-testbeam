#!/usr/bin/env python3
"""S39a CFD/template timing versus learned waveform alignment."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s39a_1784176161_696_69ab6710_cfd_template_vs_learned_waveform_alignment.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

METHOD_ORDER = [
    "traditional_cfd_template_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "waveform_transformer",
    "edge_attention_cnn_new",
]

AXES = [
    "pulse_shape_class",
    "pedestal_drift_bin",
    "pileup_separation_bin",
    "saturation_onset_bin",
    "energy_bin",
    "pid_sideband",
]


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s39a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.METHOD_ORDER = METHOD_ORDER
    return module


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
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    headers = [str(col) for col in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        values = [str(row[col]).replace("|", "\\|") for col in view.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append(
            {
                "run": int(run),
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": base.sha256_file(path),
                "role": "raw_root",
            }
        )
    return pd.DataFrame(rows)


def axis_summary(strata: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (axis, method), group in strata.groupby(["stratum", "method"], observed=False):
        if axis not in AXES or group.empty:
            continue
        group = group.copy()
        worst = group.loc[group["sigma68_ns"].idxmax()]
        best = group.loc[group["sigma68_ns"].idxmin()]
        rows.append(
            {
                "axis": str(axis),
                "method": str(method),
                "levels": int(group["level"].nunique()),
                "best_level": str(best["level"]),
                "best_sigma68_ns": float(best["sigma68_ns"]),
                "worst_level": str(worst["level"]),
                "worst_sigma68_ns": float(worst["sigma68_ns"]),
                "sigma68_span_ns": float(worst["sigma68_ns"] - best["sigma68_ns"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["axis", "sigma68_span_ns"], ascending=[True, False]).reset_index(drop=True)


def run_family_summary(predictions: pd.DataFrame, config: dict, base) -> pd.DataFrame:
    run_to_group = {}
    for family, runs in config["run_groups"].items():
        for run in runs:
            run_to_group[int(run)] = family
    held = predictions[predictions["split"].eq("heldout")].copy()
    held["run_family"] = held["run"].astype(int).map(run_to_group)
    rows = []
    for (method, family), group in held.groupby(["method", "run_family"], observed=False):
        rows.append({"method": str(method), "run_family": str(family), "n": int(len(group)), **base.metric_values(group)})
    return pd.DataFrame(rows).sort_values(["run_family", "sigma68_ns"]).reset_index(drop=True)


def write_report(
    config: dict,
    base,
    reproduction: pd.DataFrame,
    input_hashes: pd.DataFrame,
    data: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    axes: pd.DataFrame,
    families: pd.DataFrame,
    ablations: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    trad = metrics[metrics["method"].astype(str).eq("traditional_cfd_template_timewalk")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_cfd_template_timewalk", "traditional", "CFD50 residual plus monotone log-amplitude time-walk and CFD20/50 template-shape correction"],
            ["ridge", "linear ML", "standardized ridge regression on pedestal, amplitude, CFD, tail, pile-up, saturation, and waveform samples"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same leakage-controlled engineered feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform and detector-state summaries"],
            ["1d_cnn", "neural waveform", "compact convolutional regressor over the normalized 18-sample waveform window"],
            ["waveform_transformer", "new learned alignment", "one-layer sample-attention encoder with position input and amplitude-weighted pooling"],
            ["edge_attention_cnn_new", "new learned alignment", "gated edge-attention CNN that reweights leading-edge and late-curvature convolutional channels"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S39a Constant-Fraction Timing Versus Learned Waveform Alignment

## Abstract

Ticket `{config['ticket_id']}` asks whether a strong traditional
constant-fraction/template method can match or explain learned waveform timing
alignment under pedestal wander and pulse-shape changes.  This study rebuilds
the registered B-stack selected-pulse count directly from raw ROOT files,
constructs a run-held-out timing residual benchmark from the same waveforms,
and compares a CFD/template/time-walk baseline with ridge, gradient-boosted
trees, MLP, 1D-CNN, a compact transformer, and a new gated edge-attention CNN.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`{winner}`** as the
winner: `sigma_68 = {best['sigma68_ns']:.4g} ns`
`[{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.  The
traditional CFD/template reference obtains `{trad['sigma68_ns']:.4g} ns`
`[{trad['sigma68_ns_ci_low']:.4g}, {trad['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are read from `{config['raw_root_dir']}`.  For each run, `h101/HRDv`
is reshaped into eight channels and `{config['samples_per_channel']}` samples.
For each B-stack channel `c`, the pedestal and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced raw number is

`N = sum_e sum_{{c in B2,B4,B6,B8}} 1[A_{{e,c}} > {config['amplitude_cut_adc']:.0f} ADC]`.

The benchmark proceeds only after this ROOT-derived count matches the
registered anchor.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
Input hashes are stored in `input_sha256.csv`; first rows:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimand and Equations

Constant-fraction time at fraction `f` is the pre-peak linear interpolation

`t_f = k - 1 + (f A - y_{{k-1}}) / (y_k - y_{{k-1}})`,

where `y_t = x_t - b`, `y_{{k-1}} < fA <= y_k`, and the crossing index `k`
cannot exceed the waveform peak.  The prediction target is a run/stave-centered
CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

For method `m`, `epsilon_i^m = y_i - hat y_i^m`.  The resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with signed bias `median(epsilon)`.  The traditional comparator is

`hat y_trad = r_50 + g(log(1 + A)) + alpha + beta (t_0.50 - t_0.20)`,

where `r_50` is the run/stave-centered CFD50 residual and `g` is a
non-increasing isotonic time-walk correction fitted on training runs.

## Split, Uncertainty, and Leakage Controls

The split unit is the run.  Held-out runs are `{config['heldout_runs']}`; all
other configured B-stack runs train the models.  The sampled benchmark rows are:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` percentile
bootstrap replicates that resample held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

No model receives run number, event number, or split indicator.  Pedestal
wander and pulse-shape changes enter only through waveform-derived quantities:
baseline displacement, pretrigger slope, normalized samples, tail fraction, late
prominence, and flat-top occupancy.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The compact transformer is included because sample attention can express
sub-window alignment without hand-specifying an onset index.  The
`edge_attention_cnn_new` architecture is the ticket-specific new model: a
gated convolutional encoder in which a waveform-derived gate emphasizes
leading-edge samples and suppresses nuisance late-curvature channels when they
do not help timing.

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Paired Deltas Against CFD/Template

Positive `delta_sigma68_ns` means the learned method is wider than the
traditional CFD/template reference under matched held-out run-block bootstrap.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns'])}

## Run-Split Stability

{md_table(families, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=60)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=90)}

## Pedestal and Pulse-Shape Stress Tables

Stress axes are raw-waveform proxies: pedestal drift is absolute baseline
displacement from the run/stave median; pulse-shape class is late-tail fraction;
pile-up proximity is late secondary prominence spacing; saturation onset is
high amplitude or flat-top occupancy; energy proxy is amplitude quartile; PID
sideband is duplicate-readout amplitude ratio.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=180)}

Axis-compressed view:

{md_table(axes, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=80)}

## Systematic Ablations

The ablations use the gradient-boosted-tree learner and remove feature families
to test whether learned timing is mostly amplitude/CFD interpolation, pedestal
state, or late pulse-shape information.

{md_table(ablations, ['ablation', 'n_features', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Interpretation, Systematics, and Caveats

This is a comparative alignment benchmark, not an external timing-truth
measurement.  The ROOT tree provides digitized waveforms but not independent
particle truth, electronics-state labels, or picosecond reference timing.
Therefore, the analysis supports claims about relative method behavior on a
reproducible waveform-derived residual, not absolute beamline timing.

The run-block bootstrap targets transfer across data-taking periods and can be
wider than event-level uncertainty.  Small strata, especially close pile-up and
near-saturation levels, must be interpreted with their row counts.  Neural
models are compact and trained on a fixed small epoch budget; this tests whether
learned waveform alignment naturally beats a strong CFD/template construction,
not whether exhaustive neural architecture search can eventually overfit this
proxy target.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    base = load_base()
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    input_hashes = input_sha256_table(config, base)
    input_hashes.to_csv(out / "input_sha256.csv", index=False)

    data = base.sample_pulses(config, rng)
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)

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
    predictions.to_csv(out / "predictions.csv.gz", index=False)

    metrics, by_run, strata, deltas = base.summarize(predictions, config, rng)
    axes = axis_summary(strata)
    families = run_family_summary(predictions, config, base)
    ablations = base.ablation_study(data, rng)

    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    axes.to_csv(out / "frontier_axis_summary.csv", index=False)
    families.to_csv(out / "run_family_summary.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(base.raw_root_dir(config)),
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
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
        "methods": METHOD_ORDER,
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
        "metric_table": json_safe(metrics.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "frontier_axis_table": json_safe(axes.to_dict("records")),
        "run_family_table": json_safe(families.to_dict("records")),
        "ablation_table": json_safe(ablations.to_dict("records")),
        "strata_axes": AXES,
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, base, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, result, runtime)


if __name__ == "__main__":
    main()
