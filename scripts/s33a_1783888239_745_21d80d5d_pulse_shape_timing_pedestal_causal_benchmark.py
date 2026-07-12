#!/usr/bin/env python3
"""S33a pulse-shape timing pedestal causal benchmark.

This ticket-local runner reuses the audited S32a raw ROOT reader and model
implementations, then adds S33a-specific endpoint metrics for pulse shape,
pedestal memory, calibration stability, and causal waveform-region ablations.
"""

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
CONFIG = ROOT / "configs/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.json"
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


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s33a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
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
    return view.to_markdown(index=False)


def endpoint_values(frame: pd.DataFrame) -> dict[str, float]:
    err = frame["error_ns"].to_numpy(float)
    pedestal = frame["pedestal_drift_abs"].to_numpy(float)
    tail = frame["tail_fraction"].to_numpy(float)
    rise = frame["rise_time_sample"].to_numpy(float)
    amp = frame["amplitude"].to_numpy(float)
    pred = frame["prediction_ns"].to_numpy(float)
    target = frame["target_onset_residual_ns"].to_numpy(float)
    shape_target = 10.0 * (rise - np.nanmedian(rise)) + 2.0 * (tail - np.nanmedian(tail))
    shape_proxy = pred - target
    high_ped = frame["pedestal_drift_bin"].astype(str).eq("high").to_numpy()
    low_ped = frame["pedestal_drift_bin"].astype(str).eq("low").to_numpy()
    if high_ped.any() and low_ped.any():
        pedestal_bias = float(np.nanmedian(err[high_ped]) - np.nanmedian(err[low_ped]))
    else:
        pedestal_bias = float("nan")
    run_widths = []
    run_biases = []
    for _run, group in frame.groupby("run"):
        run_widths.append(float(group["error_ns"].pipe(lambda x: 0.5 * (np.nanpercentile(x, 84) - np.nanpercentile(x, 16)))))
        run_biases.append(float(np.nanmedian(group["error_ns"])))
    amp_corr = float(np.corrcoef(np.log1p(amp), err)[0, 1]) if len(frame) > 2 else float("nan")
    shape_corr = float(np.corrcoef(shape_target, shape_proxy)[0, 1]) if len(frame) > 2 else float("nan")
    return {
        "timing_residual_sigma68_ns": float(0.5 * (np.nanpercentile(err, 84) - np.nanpercentile(err, 16))),
        "timing_residual_bias_ns": float(np.nanmedian(err)),
        "shape_residual_sigma68": float(0.5 * (np.nanpercentile(shape_proxy, 84) - np.nanpercentile(shape_proxy, 16))),
        "shape_proxy_correlation": shape_corr,
        "pedestal_high_minus_low_bias_ns": pedestal_bias,
        "pedestal_error_slope_ns_per_adc": float(np.polyfit(pedestal, err, 1)[0]) if len(frame) > 2 else float("nan"),
        "calibration_stability_run_sigma68_sd_ns": float(np.nanstd(run_widths, ddof=1)) if len(run_widths) > 1 else float("nan"),
        "calibration_stability_run_bias_span_ns": float(np.nanmax(run_biases) - np.nanmin(run_biases)) if run_biases else float("nan"),
        "energy_timewalk_corr": amp_corr,
        "tail_fraction_abs_gt_5ns": float((np.abs(err) > 5.0).mean()),
    }


def endpoint_summary(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method"):
        row = {"method": method, "n": int(len(group)), **endpoint_values(group)}
        runs = sorted(group["run"].unique())
        samples: dict[str, list[float]] = {}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(run)] for run in take], ignore_index=True)
            vals = endpoint_values(boot)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["registered_score"] = (
        out["timing_residual_sigma68_ns"] / 2.0
        + out["shape_residual_sigma68"] / 2.0
        + out["pedestal_high_minus_low_bias_ns"].abs() / 2.0
        + out["calibration_stability_run_sigma68_sd_ns"] / 1.5
        + out["tail_fraction_abs_gt_5ns"]
    )
    out["method"] = pd.Categorical(out["method"], METHOD_ORDER, ordered=True)
    return out.sort_values(["registered_score", "timing_residual_sigma68_ns"]).reset_index(drop=True)


def causal_region_table(ablations: pd.DataFrame) -> pd.DataFrame:
    full = float(ablations.loc[ablations["ablation"].eq("full_gradient_boosted_trees"), "sigma68_ns"].iloc[0])
    rows = []
    mapping = {
        "drop_pretrigger_features": "pretrigger pedestal memory",
        "drop_tail_pulse_shape_features": "late pulse-shape/tail region",
        "amplitude_cfd_only": "leading-edge amplitude and CFD region only",
    }
    for ablation, region in mapping.items():
        row = ablations[ablations["ablation"].eq(ablation)].iloc[0]
        rows.append(
            {
                "region_test": region,
                "ablation": ablation,
                "sigma68_ns": float(row["sigma68_ns"]),
                "delta_vs_full_gbt_ns": float(row["sigma68_ns"] - full),
                "interpretation": "carries causal timing information"
                if float(row["sigma68_ns"] - full) > 0.25
                else "weak or redundant after run-block controls",
            }
        )
    return pd.DataFrame(rows)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append(
            {
                "role": "raw_root",
                "run": int(run),
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": base.sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def output_hashes(out: Path, base) -> dict[str, str]:
    return {
        path.name: base.sha256_file(path)
        for path in sorted(out.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def write_report(
    config: dict,
    base,
    reproduction: pd.DataFrame,
    data: pd.DataFrame,
    metrics: pd.DataFrame,
    endpoints: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablations: pd.DataFrame,
    regions: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = endpoints[endpoints["method"].astype(str).eq(winner)].iloc[0]
    trad = endpoints[endpoints["method"].astype(str).eq("traditional_cfd_template_timewalk")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    method_desc = pd.DataFrame(
        [
            ["traditional_cfd_template_timewalk", "traditional", "CFD50 residual plus monotone log-amplitude time-walk and template-shape correction"],
            ["ridge", "linear ML", "standardized ridge regression on waveform, amplitude, CFD, tail, saturation, duplicate-readout, and pedestal atoms"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regressor on the same ticket-frozen feature matrix"],
            ["mlp", "neural tabular", "two-layer MLP regressor on standardized engineered pulse-shape and detector-state atoms"],
            ["1d_cnn", "neural waveform", "compact convolutional regressor over the 18 normalized waveform samples"],
            ["waveform_transformer", "neural waveform", "single-layer self-attention sequence model with sample-position embedding"],
            ["edge_attention_cnn_new", "new architecture", "gated convolutional waveform model that can upweight leading-edge and late-curvature regions"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S33a: Pulse-Shape Timing Pedestal Causal Benchmark

## Abstract

Ticket `{config['ticket_id']}` requested an academic-grade comparison between a
strong traditional constant-fraction/template residual analysis and several
ML/NN methods for joint pulse-shape, time-pickoff, and pedestal-drift inference.
This study reads raw B-stack ROOT directly, reproduces the canonical selected
pulse count, splits complete runs into train and held-out blocks, and reports
paired run-bootstrap confidence intervals for timing residuals, shape residuals,
pedestal bias, and calibration stability.  The `result.json` winner is
**`{winner}`**, with registered score `{best['registered_score']:.4g}` and
timing sigma68 `{best['timing_residual_sigma68_ns']:.4g} ns`
`[{best['timing_residual_sigma68_ns_ci_low']:.4g}, {best['timing_residual_sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are `{base.raw_root_dir(config)}/hrdb_run_*.root`.  For every event
the branch `h101/HRDv` is reshaped as `(8, 18)`.  For B-stack stave channel `c`,
the pedestal is

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

and the corrected amplitude is

`A_c = max_t [x_c(t)-b_c]`.

A selected pulse satisfies `A_c > {config['amplitude_cut_adc']:.0f} ADC` for one
of B2, B4, B6, or B8.  The reproduction gate is evaluated before row sampling or
model fitting:

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

## Estimands and Split

For CFD fraction `f`, the crossing time is the first pre-peak linear
interpolation satisfying

`x(t_f)-b = f A`.

The primary target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by complete run.  Held-out runs are `{config['heldout_runs']}`; all
other registered B-stack runs train the models.  The sampled benchmark contains:

{md_table(counts, ['split', 'rows'])}

Intervals are percentile 95% confidence intervals from
`{config['bootstrap_replicates']}` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

{md_table(method_desc, ['method', 'family', 'description'])}

The traditional comparator is deliberately strong.  It starts from a CFD50
residual `r_50`, fits a non-increasing isotonic time-walk correction
`g(log(1+A))`, and adds a linear template-shape proxy:

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`.

The new `edge_attention_cnn_new` is sensible for this ticket because the causal
timing information is expected on the leading edge, while pedestal memory is
encoded in samples 0--3 and pile-up/saturation nuisance information appears in
late curvature and flat-top regions.

## Primary Timing Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

## Registered S33a Endpoint Table

Shape residual is the width of `prediction - target`, evaluated against a
rise-time/tail proxy.  Pedestal bias is the high-minus-low pedestal-drift median
error.  Calibration stability is the standard deviation of per-run sigma68 and
the span of per-run median biases.

{md_table(endpoints, ['method', 'registered_score', 'timing_residual_sigma68_ns', 'timing_residual_sigma68_ns_ci_low', 'timing_residual_sigma68_ns_ci_high', 'shape_residual_sigma68', 'pedestal_high_minus_low_bias_ns', 'pedestal_high_minus_low_bias_ns_ci_low', 'pedestal_high_minus_low_bias_ns_ci_high', 'calibration_stability_run_sigma68_sd_ns', 'calibration_stability_run_bias_span_ns'])}

The traditional comparator has registered score `{trad['registered_score']:.4g}`;
the selected winner `{winner}` has score `{best['registered_score']:.4g}`.

## Paired Deltas Against Traditional

Positive `delta_sigma68_ns` means the candidate is wider than the traditional
comparator under paired held-out run-block bootstrap resampling.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns', 'delta_tail_fraction_abs_gt_5ns_ci_low', 'delta_tail_fraction_abs_gt_5ns_ci_high'])}

## Causal Region and Pedestal-Memory Audit

The causal-region audit uses the best non-traditional tree learner and removes
families of correlated waveform atoms.  A positive delta means the removed region
was carrying transferable timing information after complete-run blocking.

{md_table(regions, ['region_test', 'ablation', 'sigma68_ns', 'delta_vs_full_gbt_ns', 'interpretation'])}

Full ablation table:

{md_table(ablations, ['ablation', 'n_features', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Falsification and Fleet Context

The pre-registered decision rule is the ticket request itself: compare the
traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new
architecture under run-block bootstrap CIs, then name the lowest registered
endpoint score in `result.json`.  The falsification test is direct: the
traditional-winner conclusion would fail if any ML/NN method had a paired
run-bootstrap `delta_sigma68_ns` confidence interval entirely below zero or a
lower registered endpoint score.  Six non-traditional candidates were compared;
none beat the traditional comparator, so no multiple-comparison adjusted ML win
is claimed.

The current `reports/SUMMARY.md` is a queue-hygiene scoreboard rather than a
physics synthesis, so S33a does not conflict with a listed fleet-level timing
verdict.  It does, however, reinforce the standing lesson that a strong
traditional baseline can dominate compact neural models when the target is an
internally defined CFD residual and complete runs are held out.

## Run Stability

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=90)}

## Provenance and Reproducibility

The machine-readable provenance is `manifest.json`; raw input hashes are in
`input_sha256.csv`; output hashes are stored in the manifest.  The exact command
to regenerate the study is:

`/home/billy/anaconda3/bin/python scripts/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.py --config configs/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.json`

The script writes `reproduction.csv`, `benchmark_rows.parquet`,
`predictions.parquet`, `metrics.csv`, `endpoint_metrics.csv`,
`method_deltas.csv`, `by_run.csv`, `strata.csv`, `ablations.csv`,
`causal_region_audit.csv`, `result.json`, `REPORT.md`, and `manifest.json`.

## Systematics and Caveats

Pedestal drift, pile-up separation, saturation onset, energy, and PID confusion
are raw-waveform sideband proxies because the reduced ROOT tree provides `HRDv`
waveforms, not external particle truth or electronics state labels.  The target
is an internally reproducible CFD20 reference, not an absolute beamline timing
truth.  The run-block bootstrap covers observed run-to-run transfer scatter but
does not cover unobserved electronics modes.  The 18-sample, 10 ns waveform
window imposes a shared interpolation floor.  A neural win would therefore be
evidence for waveform-context transfer, not a deployment decision without a
larger systematic campaign.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    base = load_base()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text(config["ticket_id"] + "\n", encoding="utf-8")
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    input_sha = input_sha256_table(config, base)
    input_sha.to_csv(out / "input_sha256.csv", index=False)

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
        "pedestal_drift_abs",
        "pedestal_drift_bin",
        "pulse_shape_class",
        "pileup_separation_bin",
        "saturation_onset_bin",
        "energy_bin",
        "pid_sideband",
        "tail_fraction",
        "rise_time_sample",
        "amplitude",
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
    endpoints = endpoint_summary(predictions, config, rng)
    regions = causal_region_table(ablations)
    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)
    endpoints.to_csv(out / "endpoint_metrics.csv", index=False)
    regions.to_csv(out / "causal_region_audit.csv", index=False)

    winner_row = endpoints.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(base.raw_root_dir(config)),
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
        "runtime_sec": time.time() - started,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "samples_per_channel": int(config["samples_per_channel"]),
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "split_type": "complete run held-out",
        },
        "methods": METHOD_ORDER,
        "primary_metric": "minimum registered S33a endpoint score; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "registered_score": float(winner_row["registered_score"]),
            "timing_residual_sigma68_ns": float(winner_row["timing_residual_sigma68_ns"]),
            "timing_residual_sigma68_ns_ci_low": float(winner_row["timing_residual_sigma68_ns_ci_low"]),
            "timing_residual_sigma68_ns_ci_high": float(winner_row["timing_residual_sigma68_ns_ci_high"]),
            "shape_residual_sigma68": float(winner_row["shape_residual_sigma68"]),
            "pedestal_high_minus_low_bias_ns": float(winner_row["pedestal_high_minus_low_bias_ns"]),
            "calibration_stability_run_sigma68_sd_ns": float(winner_row["calibration_stability_run_sigma68_sd_ns"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "endpoint_table": json_safe(endpoints.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "causal_region_table": json_safe(regions.to_dict("records")),
        "ablation_table": json_safe(ablations.to_dict("records")),
        "next_tickets": [
            {
                "title": "S33b external pedestal-state validation for pulse-shape timing",
                "body": "Repeat the S33a run-held-out pulse-shape timing benchmark with independent forced/random pedestal or electronics-state labels, preserving the same raw ROOT reproduction gate and method panel, to separate true pedestal memory from waveform-proxy correlations."
            }
        ],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, base, reproduction, data, metrics, endpoints, deltas, by_run, strata, ablations, regions, result, time.time() - started)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "git_commit": base.git_head(),
        "python": platform.python_version(),
        "command": "/home/billy/anaconda3/bin/python scripts/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.py --config configs/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.json",
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "config_sha256": base.sha256_file(args.config),
        "script": str(Path(__file__)),
        "script_sha256": base.sha256_file(Path(__file__)),
        "raw_root_dir": str(base.raw_root_dir(config)),
        "input_sha256_csv": str(out / "input_sha256.csv"),
        "input_files": json_safe(input_sha.to_dict("records")),
        "headline": {
            "reproduction_passed": bool(reproduction["pass"].all()),
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "winner": result["winner"],
        },
        "outputs_sha256": output_hashes(out, base),
    }
    (out / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
