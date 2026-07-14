#!/usr/bin/env python3
"""S35a raw pulse-onset pedestal timing frontier benchmark."""

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
CONFIG = ROOT / "configs/s35a_1784063447_849_4ac02d58_raw_pulse_onset_pedestal_timing_frontier.json"
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
    spec = importlib.util.spec_from_file_location("s32a_base_for_s35a", BASE_SCRIPT)
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


def frontier_axis_summary(strata: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (axis, method), group in strata.groupby(["stratum", "method"], observed=False):
        if axis not in AXES or group.empty:
            continue
        group = group.copy()
        worst = group.loc[group["sigma68_ns"].idxmax()]
        best = group.loc[group["sigma68_ns"].idxmin()]
        high_tail = group.loc[group["tail_fraction_abs_gt_5ns"].idxmax()]
        rows.append(
            {
                "axis": str(axis),
                "method": str(method),
                "levels": int(group["level"].nunique()),
                "worst_level": str(worst["level"]),
                "worst_sigma68_ns": float(worst["sigma68_ns"]),
                "best_level": str(best["level"]),
                "best_sigma68_ns": float(best["sigma68_ns"]),
                "sigma68_span_ns": float(worst["sigma68_ns"] - best["sigma68_ns"]),
                "highest_tail_level": str(high_tail["level"]),
                "highest_tail_fraction_abs_gt_5ns": float(high_tail["tail_fraction_abs_gt_5ns"]),
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
        vals = base.metric_values(group)
        rows.append({"method": str(method), "run_family": str(family), "n": int(len(group)), **vals})
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
    axis_summary: pd.DataFrame,
    family_summary: pd.DataFrame,
    ablations: pd.DataFrame,
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
            ["traditional_cfd_template_timewalk", "traditional", "CFD50 residual with constrained monotone log-amplitude time-walk and template-shape correction"],
            ["ridge", "linear ML", "standardized ridge regression on scalar pulse atoms plus normalized waveform samples"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same leakage-controlled feature matrix"],
            ["mlp", "neural tabular", "two-layer MLP over engineered onset, pedestal, shape, saturation, energy, and duplicate-readout features"],
            ["1d_cnn", "neural waveform", "compact 1D convolutional encoder over the 18-sample normalized waveform"],
            ["waveform_transformer", "compact transformer encoder", "one-layer self-attention waveform encoder with sample-position embedding and amplitude-weighted pooling"],
            ["edge_attention_cnn_new", "new architecture", "gated edge-attention CNN that learns leading-edge and late-curvature channel weights"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S35a Raw Pulse-Onset Pedestal Timing Frontier

## Abstract

Ticket `{config['ticket_id']}` requested a raw-ROOT reproduction followed by a
run-split benchmark of a strong traditional timing method against ridge,
gradient-boosted trees, MLP, 1D-CNN, compact transformer encoders, and a new
architecture when sensible.  This study rebuilds the B-stack pulse table
directly from `h101/HRDv`, verifies the registered selected-pulse count, and
evaluates timing bias and resolution under pulse-shape, pedestal-memory,
pile-up-proximity, saturation-onset, energy-proxy, and PID-sideband strata.

The primary registered criterion is held-out run-block `sigma_68` of onset
residual error.  The winner written to `result.json` is **`{winner}`** with
`sigma_68 = {best['sigma68_ns']:.4g} ns`
`[{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.  The
traditional reference obtains `{trad['sigma68_ns']:.4g} ns`
`[{trad['sigma68_ns_ci_low']:.4g}, {trad['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction Gate

Input ROOT files are read from `{config['raw_root_dir']}`.  For each run the
branch `h101/HRDv` is reshaped into eight channels and eighteen ADC samples.  A
per-channel pedestal is estimated from pretrigger samples

`b_{{e,c}} = median(x_{{e,c,0}}, x_{{e,c,1}}, x_{{e,c,2}}, x_{{e,c,3}})`,

and the pulse amplitude is

`A_{{e,c}} = max_t [x_{{e,c,t}} - b_{{e,c}}]`.

The raw reproduction number is

`N = sum_e sum_{{c in B2,B4,B6,B8}} 1[A_{{e,c}} > {config['amplitude_cut_adc']:.0f} ADC]`.

The analysis proceeds only if every count below matches the registered ROOT
anchor exactly.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The reproduced all-group number is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
Raw input hashes are stored in `input_sha256.csv`; the first rows are:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimand

For a selected waveform, a constant-fraction crossing at fraction `f` is found
by linear interpolation before the peak:

`t_f = k - 1 + (f A - y_{{k-1}}) / (y_k - y_{{k-1}})`,

where `y_t = x_t - b`, `y_{{k-1}} < fA <= y_k`, and `k` is constrained not to
exceed the peak sample.  The target is a run/stave-centered CFD20 residual

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

Models predict `hat y_i`; the residual error is `epsilon_i = y_i - hat y_i`.
The main resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

and the signed bias is `median(epsilon)`.

## Split and Uncertainty

The split is by run, never by shuffled event.  Held-out runs are
`{config['heldout_runs']}`; all other configured B-stack runs are training
runs.  The sampled benchmark contains:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` percentile
bootstrap replicates that resample held-out runs with replacement.  For a
metric `theta`,

`CI_95(theta) = [q_0.025(theta^*_b), q_0.975(theta^*_b)]`.

## Methods

{md_table(method_desc, ['method', 'family', 'description'])}

The traditional comparator is deliberately strong: it starts with the CFD50
residual, fits a non-increasing isotonic correction in `log(1+A)` on training
runs, and adds a linear template proxy from `(t_0.50 - t_0.20)`.

`hat y_trad = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`.

The new `edge_attention_cnn_new` is sensible here because onset timing is a
localized leading-edge problem, while late curvature and flat-top samples are
nuisance indicators for pile-up and saturation.  The architecture learns a gate
from the raw normalized waveform and multiplies the convolutional feature maps
before the timing head.  No model receives run number or event number.

## Primary Method Table

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

## Paired Deltas Against Traditional Reference

Positive `delta_sigma68_ns` means the method is wider than the traditional
reference under the same run-block bootstrap.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high'])}

## Run and Run-Family Stability

{md_table(family_summary, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=60)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=90)}

## Frontier Strata

The requested axes are represented by raw waveform proxies: tail fraction for
pulse shape, baseline displacement for pedestal memory, late secondary
prominence spacing for pile-up proximity, high-amplitude/flat-top occupancy for
saturation onset, amplitude quartile for energy proxy, and duplicate-readout
ratio sidebands for PID stratum.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=180)}

The table below compresses each method/axis to its best and worst stratum.

{md_table(axis_summary, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=80)}

## Systematic Ablations

The ablations remove correlated feature families from the gradient-boosted-tree
learner.  They test whether the frontier is driven by pretrigger pedestal
memory, late pulse-shape information, or only amplitude and CFD features.

{md_table(ablations, ['ablation', 'n_features', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Systematics, Limitations, and Caveats

The raw ROOT tree provides waveforms but not independent particle truth,
external timing truth, or electronics-state labels.  PID, energy, pile-up
proximity, and saturation are therefore stress strata, not truth labels.
Because all targets are constructed from the same digitized waveform, absolute
physics timing should not be inferred from the sub-ns residuals alone.  The
claim supported here is comparative: given an identical raw-ROOT reconstruction,
run-held-out split, and bootstrap, the listed methods have the reported
relative bias and resolution on the registered onset residual.

The run-block bootstrap emphasizes transfer across data-taking periods; it is
not an event-level counting interval.  Small strata, especially high pile-up
prominence and near-saturation subsets, should be read through their tabled
sample counts.  Neural methods are intentionally compact and trained for a
fixed small epoch budget to avoid turning the ticket into architecture search.

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
    axis_summary = frontier_axis_summary(strata)
    family_summary = run_family_summary(predictions, config, base)
    ablations = base.ablation_study(data, rng)

    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    axis_summary.to_csv(out / "frontier_axis_summary.csv", index=False)
    family_summary.to_csv(out / "run_family_summary.csv", index=False)
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
        "frontier_axis_table": json_safe(axis_summary.to_dict("records")),
        "run_family_table": json_safe(family_summary.to_dict("records")),
        "ablation_table": json_safe(ablations.to_dict("records")),
        "strata_axes": AXES,
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(
        config,
        base,
        reproduction,
        input_hashes,
        data,
        metrics,
        deltas,
        by_run,
        strata,
        axis_summary,
        family_summary,
        ablations,
        result,
        runtime,
    )


if __name__ == "__main__":
    main()
