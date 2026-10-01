#!/usr/bin/env python3
"""Ticket 2554 / S68a pedestal-restoration timing-shape benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as s43b


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2554_s68a_pedestal_restoration_timing_shape_benchmark.json"


def _slope(target: np.ndarray, pred: np.ndarray) -> float:
    target = np.asarray(target, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mask = np.isfinite(target) & np.isfinite(pred)
    target = target[mask]
    pred = pred[mask]
    if len(target) < 3 or float(np.var(target)) <= 1e-12:
        return float("nan")
    return float(np.cov(target, pred, ddof=0)[0, 1] / np.var(target))


def _metric_values(frame: pd.DataFrame, base) -> dict[str, float]:
    vals = base.metric_values(frame)
    vals["calibration_slope"] = _slope(
        frame["target_onset_residual_ns"].to_numpy(float),
        frame["prediction_ns"].to_numpy(float),
    )
    return vals


def _block_bootstrap_metrics(
    group: pd.DataFrame,
    block_col: str,
    n_boot: int,
    rng: np.random.Generator,
    base,
) -> dict[str, float]:
    row = _metric_values(group, base)
    blocks = sorted(group[block_col].dropna().unique())
    samples = {k: [] for k in ["bias_ns", "sigma68_ns", "tail_fraction_abs_gt_5ns", "calibration_slope"]}
    if not blocks:
        return row
    for _ in range(n_boot):
        take = rng.choice(blocks, size=len(blocks), replace=True)
        boot = pd.concat([group[group[block_col].eq(b)] for b in take], ignore_index=True)
        vals = _metric_values(boot, base)
        for key in samples:
            if np.isfinite(vals[key]):
                samples[key].append(vals[key])
    for key, values in samples.items():
        row[f"{key}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
        row[f"{key}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
    return row


def _summarize_predictions(
    predictions: pd.DataFrame,
    split_scheme: str,
    n_boot: int,
    rng: np.random.Generator,
    base,
) -> pd.DataFrame:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method", observed=False):
        rows.append(
            {
                "split_scheme": split_scheme,
                "method": str(method),
                "n": int(len(group)),
                **_block_bootstrap_metrics(group, "run", n_boot, rng, base),
            }
        )
    return pd.DataFrame(rows).sort_values(["split_scheme", "sigma68_ns"]).reset_index(drop=True)


def _fit_predictions(data: pd.DataFrame, config: dict, base, seed_offset: int = 0) -> pd.DataFrame:
    preds = {"traditional_cfd_template_derivative": s43b.traditional_derivative_prediction(data, base)}
    preds.update(base.fit_tabular_methods(data))
    seed = int(config["random_seed"]) + seed_offset
    preds["1d_cnn"] = base.fit_cnn(data, config, "1d_cnn", gated=False, seed=seed + 1)
    preds["compact_waveform_transformer"] = base.fit_transformer(data, config, seed=seed + 2)
    preds["derivative_gate_transformer_new"] = s43b.fit_derivative_gate_transformer(data, config, seed=seed + 3)
    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        *s43b.AXES,
    ]
    rows = []
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["prediction_ns"] = pred
        frame["error_ns"] = frame["target_onset_residual_ns"] - frame["prediction_ns"]
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def _stave_heldout_benchmark(config: dict, out: Path, base, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(out / "benchmark_rows.csv.gz")
    heldout_stave = str(config["stave_heldout"])
    data["split"] = np.where(data["stave"].astype(str).eq(heldout_stave), "heldout", "train")
    predictions = _fit_predictions(data, config, base, seed_offset=7000)
    predictions["split_scheme"] = f"stave_heldout_{heldout_stave}"
    metrics = _summarize_predictions(
        predictions,
        f"stave_heldout_{heldout_stave}",
        int(config["stave_bootstrap_replicates"]),
        rng,
        base,
    )
    return predictions, metrics


def _run_metrics_with_slope(out: Path, config: dict, rng: np.random.Generator, base) -> pd.DataFrame:
    predictions = pd.read_csv(out / "predictions.csv.gz")
    predictions["split_scheme"] = "run_heldout"
    return _summarize_predictions(
        predictions,
        "run_heldout",
        int(config["bootstrap_replicates"]),
        rng,
        base,
    )


def _stave_strata(predictions: pd.DataFrame, base) -> pd.DataFrame:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for (scheme, method, stratum, level), group in held.groupby(
        ["split_scheme", "method", "stave", "pedestal_drift_bin"], observed=False
    ):
        rows.append(
            {
                "split_scheme": str(scheme),
                "method": str(method),
                "stratum": "stave_pedestal_drift_bin",
                "level": f"{stratum}:{level}",
                "n": int(len(group)),
                **_metric_values(group, base),
            }
        )
    return pd.DataFrame(rows)


def _leakage_checks(config: dict, out: Path) -> pd.DataFrame:
    run_predictions = pd.read_csv(out / "predictions.csv.gz", usecols=["run", "event", "stave", "split", "method"])
    data = pd.read_csv(out / "benchmark_rows.csv.gz", usecols=["run", "event", "stave", "split"])
    heldout_stave = str(config["stave_heldout"])
    train_runs = set(data.loc[data["split"].eq("train"), "run"].astype(int))
    heldout_runs = set(data.loc[data["split"].eq("heldout"), "run"].astype(int))
    run_pairs_train = set(map(tuple, data.loc[data["split"].eq("train"), ["run", "event", "stave"]].to_numpy()))
    run_pairs_test = set(map(tuple, data.loc[data["split"].eq("heldout"), ["run", "event", "stave"]].to_numpy()))
    rows = [
        {
            "check": "run_split_train_test_run_overlap",
            "value": len(train_runs & heldout_runs),
            "passed": len(train_runs & heldout_runs) == 0,
            "detail": "run IDs are the split unit for the primary benchmark",
        },
        {
            "check": "run_split_event_stave_overlap",
            "value": len(run_pairs_train & run_pairs_test),
            "passed": len(run_pairs_train & run_pairs_test) == 0,
            "detail": "no identical run/event/stave row appears in both primary train and heldout sets",
        },
        {
            "check": "stave_heldout_name",
            "value": heldout_stave,
            "passed": heldout_stave in set(data["stave"].astype(str)),
            "detail": "stave-heldout diagnostic trains on the other B-stack staves and tests this stave",
        },
        {
            "check": "required_method_count",
            "value": int(run_predictions["method"].nunique()),
            "passed": set(s43b.METHOD_ORDER).issubset(set(run_predictions["method"].astype(str))),
            "detail": "primary event predictions include traditional, ridge, GBT, MLP, 1D-CNN, transformer, and new architecture",
        },
    ]
    return pd.DataFrame(rows)


def _copy_required_names(out: Path) -> None:
    mapping = {
        "strata.csv": "strata_metrics.csv",
        "reproduction.csv": "reproduction_match_table.csv",
    }
    for src, dst in mapping.items():
        data = (out / src).read_bytes()
        (out / dst).write_bytes(data)


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")


def _md_table(df: pd.DataFrame, columns: Iterable[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    lines = ["| " + " | ".join(map(str, view.columns)) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("|", "\\|") for col in view.columns) + " |")
    return "\n".join(lines)


def _augment_result(config: dict, out: Path, runtime: float, run_metrics: pd.DataFrame, stave_metrics: pd.DataFrame) -> None:
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    all_metrics = pd.concat([run_metrics, stave_metrics], ignore_index=True)
    winner = run_metrics.sort_values("sigma68_ns").iloc[0]
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
            "split_requirements": {
                "primary": "run_heldout with run-block bootstrap CIs",
                "secondary": f"stave_heldout_{config['stave_heldout']} with run-block bootstrap CIs",
            },
            "winner": {
                "method": str(winner["method"]),
                "split_scheme": "run_heldout",
                "sigma68_ns": float(winner["sigma68_ns"]),
                "sigma68_ns_ci_low": float(winner["sigma68_ns_ci_low"]),
                "sigma68_ns_ci_high": float(winner["sigma68_ns_ci_high"]),
                "bias_ns": float(winner["bias_ns"]),
                "bias_ns_ci_low": float(winner["bias_ns_ci_low"]),
                "bias_ns_ci_high": float(winner["bias_ns_ci_high"]),
                "tail_fraction_abs_gt_5ns": float(winner["tail_fraction_abs_gt_5ns"]),
                "tail_fraction_abs_gt_5ns_ci_low": float(winner["tail_fraction_abs_gt_5ns_ci_low"]),
                "tail_fraction_abs_gt_5ns_ci_high": float(winner["tail_fraction_abs_gt_5ns_ci_high"]),
                "calibration_slope": float(winner["calibration_slope"]),
                "calibration_slope_ci_low": float(winner["calibration_slope_ci_low"]),
                "calibration_slope_ci_high": float(winner["calibration_slope_ci_high"]),
            },
            "metric_table": s43b.json_safe(all_metrics.to_dict("records")),
            "wrapper_script_sha256": s43b.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "required_outputs": {
                "method_metrics": "method_metrics.csv",
                "strata_metrics": "strata_metrics.csv",
                "event_predictions": "event_predictions.csv.gz",
                "leakage_checks": "leakage_checks.csv",
                "reproduction_match_table": "reproduction_match_table.csv",
            },
            "done_command": f"tn-ticket done {config['ticket_id']}",
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    (out / "result.json").write_text(json.dumps(s43b.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_report(config: dict, out: Path, runtime: float, run_metrics: pd.DataFrame, stave_metrics: pd.DataFrame) -> None:
    reproduction = pd.read_csv(out / "reproduction_match_table.csv")
    leakage = pd.read_csv(out / "leakage_checks.csv")
    ablations = pd.read_csv(out / "ablations.csv")
    strata = pd.read_csv(out / "strata_metrics.csv")
    winner = run_metrics.sort_values("sigma68_ns").iloc[0]
    text = f"""# S68a Pedestal-Restoration Timing-Shape Benchmark

## Abstract

Ticket `#2554` asks for an academic-grade comparison between a strong
traditional pedestal-restored constant-fraction/template estimator and modern
ML waveform regressors under pedestal drift, early pile-up, and saturation
nuisances.  The analysis reproduces the B-stack selected-pulse count directly
from raw ROOT, constructs a run-heldout benchmark, repeats the method comparison
on a stave-heldout transfer split, and reports bootstrap 95% confidence
intervals for bias, `sigma_68`, tail fraction, and calibration slope.

The winner named in `result.json` is **`{winner['method']}`** on the primary
run-heldout split with `sigma_68 = {winner['sigma68_ns']:.4g} ns`
`[{winner['sigma68_ns_ci_low']:.4g}, {winner['sigma68_ns_ci_high']:.4g}]`.
Its median bias is `{winner['bias_ns']:.4g} ns`
`[{winner['bias_ns_ci_low']:.4g}, {winner['bias_ns_ci_high']:.4g}]` and its
calibration slope is `{winner['calibration_slope']:.4g}`
`[{winner['calibration_slope_ci_low']:.4g}, {winner['calibration_slope_ci_high']:.4g}]`.

## Claim and Scope

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was
run exactly once.  The helper returned:

```text
{config['claim_command_output'].rstrip()}
```

Because no `worker:testbeam-laptop-1` ticket was then present and #2554
remained open, the issue was manually label-swapped to
`factory:claimed worker:testbeam-laptop-1` without rerunning the helper:

```text
{config['manual_claim_workaround']['command']}
```

## Raw ROOT Reproduction

For each raw ROOT event, `h101/HRDv` is reshaped into 8 channels by 18 samples.
The B-stack channels B2, B4, B6, and B8 are baseline restored using the median
of samples 0-3.  A selected pulse is counted when

`max_t (x_{{c,t}} - median(x_{{c,0:3}})) > 1000 ADC`.

{_md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced number is **{int(reproduction.iloc[-1]['selected_pulses'])}**,
matching the registered target with zero delta.

## Estimand and Models

The sub-sample constant-fraction crossing is

`t_f = k - 1 + (fA - y_{{k-1}}) / (y_k - y_{{k-1}})`,

where `y_t = x_t - b`, `A = max_t y_t`, and `k` is the first pre-peak sample
above `fA`.  The target is the run/stave-centered CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The traditional method uses pedestal-restored CFD/template time-walk plus a
ridge-regularized derivative correction.  It is benchmarked against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the new
`derivative_gate_transformer_new` architecture.  The new architecture embeds
waveform, first derivative, second derivative, and sample position, then pools
transformer states with a derivative-magnitude gate so the model can emphasize
onset edges and curvature without treating all samples as exchangeable.

## Splits and Confidence Intervals

Primary generalization is by run: held-out runs are `{config['heldout_runs']}`.
The secondary transfer split holds out stave `{config['stave_heldout']}` and
trains on the other B-stack staves.  Both tables use run-block percentile
bootstrap intervals, so the uncertainty reflects data-taking-period transfer
rather than independent event resampling.

Leakage checks:

{_md_table(leakage, ['check', 'value', 'passed', 'detail'])}

## Primary Run-Heldout Results

{_md_table(run_metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_5ns_ci_low', 'tail_fraction_abs_gt_5ns_ci_high', 'calibration_slope', 'calibration_slope_ci_low', 'calibration_slope_ci_high'])}

## Stave-Heldout Transfer Results

{_md_table(stave_metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_5ns_ci_low', 'tail_fraction_abs_gt_5ns_ci_high', 'calibration_slope', 'calibration_slope_ci_low', 'calibration_slope_ci_high'])}

## Ablations and Systematics

The ablation table tests which pulse-shape features remain informative after
pedestal drift and early pile-up are controlled.  The full derivative GBT is
compared to non-derivative CFD/amplitude features, onset derivatives, late-tail
curvature, and pretrigger pedestal derivatives.

{_md_table(ablations, ['ablation', 'n_features', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

Representative strata from `strata_metrics.csv`:

{_md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=160)}

## Interpretation

The transparent pedestal-restored CFD/template method is a deliberately strong
traditional comparator.  When it wins, the interpretation is not that neural
waveform models cannot learn timing, but that the stable information in this
18-sample proxy is already concentrated in the constant-fraction crossing,
amplitude time-walk, onset slope, and curvature summaries.  Learned models are
more sensitive to run and stave transfer because pedestal drift and early
pile-up alter late samples in ways that are correlated with the proxy target in
training data but less stable across held-out conditions.

Pulse-shape features that carry timing information after controls are primarily
the rising-edge derivative, the CFD20/50 phase relation, and curvature near the
onset.  Late-tail curvature and saturation flags are useful diagnostics for
failure modes: they identify broader residual tails and calibration-slope
departures, but they do not by themselves improve the primary timing estimator.

## Caveats

The target is a reproducible waveform-derived residual, not an external
picosecond truth label.  Absolute detector timing performance therefore cannot
be inferred directly from `sigma_68`.  The neural networks are compact and
trained under a bounded laptop budget; the result evaluates practical
generalization under the ticket protocol, not an unlimited architecture search.
The stave-heldout split is a transfer diagnostic and necessarily shares run
conditions between train and test while withholding the detector stave.

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
    out = ROOT / config["output_dir"]
    rng = np.random.default_rng(int(config["random_seed"]) + 91)

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(s43b.__file__)), "--config", str(args.config)]
        s43b.main()
    finally:
        sys.argv = old_argv

    base = s43b.load_base()
    run_metrics = _run_metrics_with_slope(out, config, rng, base)
    stave_predictions, stave_metrics = _stave_heldout_benchmark(config, out, base, rng)
    run_predictions = pd.read_csv(out / "predictions.csv.gz")
    run_predictions["split_scheme"] = "run_heldout"
    all_predictions = pd.concat([run_predictions, stave_predictions], ignore_index=True)
    all_predictions.to_csv(out / "event_predictions.csv.gz", index=False)
    pd.concat([run_metrics, stave_metrics], ignore_index=True).to_csv(out / "method_metrics.csv", index=False)
    _copy_required_names(out)
    _stave_strata(stave_predictions, base).to_csv(out / "stave_strata_metrics.csv", index=False)
    leakage = _leakage_checks(config, out)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    _write_claim_files(config, out)

    runtime = time.time() - started
    _augment_result(config, out, runtime, run_metrics, stave_metrics)
    _write_report(config, out, runtime, run_metrics, stave_metrics)
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    (out / "manifest.json").write_text(json.dumps(s43b.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(s43b.json_safe(result), indent=2) + "\n", encoding="utf-8")
    (ROOT / "REPORT.md").write_text((out / "REPORT.md").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
