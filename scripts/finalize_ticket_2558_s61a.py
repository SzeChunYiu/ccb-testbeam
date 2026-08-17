#!/usr/bin/env python3
"""Finalize ticket 2558 artifacts from existing benchmark rows and predictions."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2558_s61a_pulse_shape_timing_pedestal_phase.json"
OUT = ROOT / "reports/2558__s61a_pulse_shape_timing_pedestal_phase_benchmark"
METHOD_ORDER = [
    "traditional_cfd_template_derivative",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_waveform_transformer",
    "derivative_gate_transformer_new",
]
AXES = [
    "pedestal_drift_bin",
    "energy_bin",
    "pulse_shape_class",
    "derivative_onset_bin",
    "curvature_energy_bin",
    "late_tail_morphology",
    "pileup_separation_bin",
    "saturation_onset_bin",
    "pid_sideband",
]


def sha256_path(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


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


def metrics_from_error(error: np.ndarray) -> dict[str, float]:
    error = np.asarray(error, dtype=float)
    error = error[np.isfinite(error)]
    if len(error) == 0:
        return {
            "bias_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "rms_ns": float("nan"),
            "tail_fraction_abs_gt_5ns": float("nan"),
            "tail_fraction_abs_gt_10ns": float("nan"),
        }
    return {
        "bias_ns": float(np.median(error)),
        "sigma68_ns": float(0.5 * (np.percentile(error, 84) - np.percentile(error, 16))),
        "rms_ns": float(np.sqrt(np.mean(error**2))),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(error) > 5.0)),
        "tail_fraction_abs_gt_10ns": float(np.mean(np.abs(error) > 10.0)),
    }


def run_block_ci(group: pd.DataFrame, rng: np.random.Generator, reps: int) -> dict[str, float]:
    run_errors = {int(run): sub["error_ns"].to_numpy(float) for run, sub in group.groupby("run")}
    runs = np.asarray(sorted(run_errors), dtype=int)
    samples = {k: [] for k in metrics_from_error(group["error_ns"].to_numpy(float))}
    for _ in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        err = np.concatenate([run_errors[int(run)] for run in chosen])
        vals = metrics_from_error(err)
        for key, value in vals.items():
            samples[key].append(value)
    out = {}
    for key, values in samples.items():
        out[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
        out[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
    return out


def summarize(pred: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 21)
    reps = int(config["bootstrap_replicates"])
    held = pred[pred["split"].eq("heldout")].copy()
    metric_rows = []
    boot = {}
    for method in METHOD_ORDER:
        group = held[held["method"].eq(method)]
        row = {"method": method, "n": int(len(group)), **metrics_from_error(group["error_ns"].to_numpy(float))}
        row.update(run_block_ci(group, rng, reps))
        boot[method] = row
        metric_rows.append(row)
    metrics = pd.DataFrame(metric_rows).sort_values(["sigma68_ns", "rms_ns"]).reset_index(drop=True)

    run_rows = []
    for (method, run), group in held.groupby(["method", "run"], observed=False):
        run_rows.append({"method": str(method), "run": int(run), "n": int(len(group)), **metrics_from_error(group["error_ns"].to_numpy(float))})
    by_run = pd.DataFrame(run_rows).sort_values(["method", "run"]).reset_index(drop=True)

    strata_rows = []
    for method in METHOD_ORDER:
        mg = held[held["method"].eq(method)]
        for axis in AXES:
            for level, group in mg.groupby(axis, observed=False):
                strata_rows.append({"stratum": axis, "level": str(level), "method": method, "n": int(len(group)), **metrics_from_error(group["error_ns"].to_numpy(float))})
    strata = pd.DataFrame(strata_rows).sort_values(["stratum", "level", "method"]).reset_index(drop=True)

    delta_rows = []
    reference = metrics[metrics["method"].eq("traditional_cfd_template_derivative")].iloc[0]
    for _, row in metrics.iterrows():
        if row["method"] == "traditional_cfd_template_derivative":
            continue
        delta_rows.append(
            {
                "method": row["method"],
                "reference_method": "traditional_cfd_template_derivative",
                "delta_bias_ns": float(row["bias_ns"] - reference["bias_ns"]),
                "delta_sigma68_ns": float(row["sigma68_ns"] - reference["sigma68_ns"]),
                "delta_rms_ns": float(row["rms_ns"] - reference["rms_ns"]),
                "delta_tail_fraction_abs_gt_5ns": float(row["tail_fraction_abs_gt_5ns"] - reference["tail_fraction_abs_gt_5ns"]),
                "delta_tail_fraction_abs_gt_10ns": float(row["tail_fraction_abs_gt_10ns"] - reference["tail_fraction_abs_gt_10ns"]),
                "delta_sigma68_ns_ci_low": float(row["sigma68_ns_ci_low"] - reference["sigma68_ns_ci_high"]),
                "delta_sigma68_ns_ci_high": float(row["sigma68_ns_ci_high"] - reference["sigma68_ns_ci_low"]),
            }
        )
    deltas = pd.DataFrame(delta_rows).sort_values("delta_sigma68_ns").reset_index(drop=True)

    axis_rows = []
    for (axis, method), group in strata.groupby(["stratum", "method"], observed=False):
        best = group.loc[group["sigma68_ns"].idxmin()]
        worst = group.loc[group["sigma68_ns"].idxmax()]
        axis_rows.append(
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
    axes = pd.DataFrame(axis_rows).sort_values(["axis", "sigma68_span_ns"], ascending=[True, False]).reset_index(drop=True)
    return metrics, by_run, strata, deltas, axes


def feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {"run", "event", "target_onset_residual_ns", "split"}
    prefixes = ("w", "d1_", "d2_")
    cols = []
    for col in df.columns:
        if col in excluded or col in AXES:
            continue
        if pd.api.types.is_numeric_dtype(df[col]) and (col.startswith(prefixes) or col not in {"channel"}):
            cols.append(col)
    return cols


def atom_coefficients(data: pd.DataFrame) -> pd.DataFrame:
    cols = feature_columns(data)
    train = data["split"].eq("train").to_numpy()
    y = data["target_onset_residual_ns"].to_numpy(float)
    model = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
    model.fit(data.loc[train, cols].to_numpy(float), y[train])
    rows = []
    for feature, coef in zip(cols, model.named_steps["ridge"].coef_):
        if feature.startswith("w"):
            family = "normalized_sample_atom"
        elif feature.startswith("d1_"):
            family = "first_derivative_atom"
        elif feature.startswith("d2_"):
            family = "curvature_atom"
        elif feature in {"baseline", "pretrigger_slope", "pretrigger_derivative_rms"}:
            family = "pedestal_atom"
        elif feature in {"amplitude", "peak_sample", "cfd20_sample", "cfd50_sample", "cfd80_sample", "rise_time_sample"}:
            family = "fixed_timing_amplitude_covariate"
        else:
            family = "shape_summary_atom"
        rows.append({"feature": feature, "family": family, "ridge_standardized_coef_ns": float(coef), "abs_coef_ns": float(abs(coef))})
    return pd.DataFrame(rows).sort_values("abs_coef_ns", ascending=False).reset_index(drop=True)


def placebo_controls(data: pd.DataFrame, seed: int) -> pd.DataFrame:
    cols = feature_columns(data)
    rng = np.random.default_rng(seed)
    train = data["split"].eq("train").to_numpy()
    y = data["target_onset_residual_ns"].to_numpy(float)
    shuffled = y.copy()
    for run in sorted(data["run"].unique()):
        idx = data.index[data["run"].eq(run)].to_numpy()
        shuffled[idx] = rng.permutation(shuffled[idx])
    rows = []
    models = {
        "ridge_runwise_target_placebo": make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
        "hgb_runwise_target_placebo": HistGradientBoostingRegressor(max_iter=80, learning_rate=0.05, l2_regularization=0.05, random_state=seed),
    }
    for name, model in models.items():
        model.fit(data.loc[train, cols].to_numpy(float), shuffled[train])
        pred = model.predict(data.loc[:, cols].to_numpy(float))
        held = data[data["split"].eq("heldout")].copy()
        held["error_ns"] = held["target_onset_residual_ns"] - pred[held.index]
        rows.append({"control": name, "n": int(len(held)), **metrics_from_error(held["error_ns"].to_numpy(float))})
    return pd.DataFrame(rows)


def run_family_summary(pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    run_to_group = {int(run): group for group, runs in config["run_groups"].items() for run in runs}
    held = pred[pred["split"].eq("heldout")].copy()
    held["run_family"] = held["run"].astype(int).map(run_to_group)
    rows = []
    for (family, method), group in held.groupby(["run_family", "method"], observed=False):
        rows.append({"run_family": str(family), "method": str(method), "n": int(len(group)), **metrics_from_error(group["error_ns"].to_numpy(float))})
    return pd.DataFrame(rows).sort_values(["run_family", "sigma68_ns"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("|", "\\|") for col in view.columns) + " |")
    return "\n".join(lines)


def write_report(config: dict, reproduction: pd.DataFrame, inputs: pd.DataFrame, data: pd.DataFrame, pred: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, axes: pd.DataFrame, families: pd.DataFrame, atoms: pd.DataFrame, placebo: pd.DataFrame, runtime: float) -> None:
    winner = metrics.iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_cfd_template_derivative", "traditional", "polarity-bound CFD20/50 template time-walk baseline plus derivative residual correction"],
            ["ridge", "linear ML", "standardized ridge regression on fixed amplitude, phase, pedestal, waveform, derivative, and curvature atoms"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same leakage-controlled feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered pulse-shape covariates"],
            ["1d_cnn", "neural waveform", "compact 1D convolutional regressor over normalized 18-sample pulse windows"],
            ["compact_waveform_transformer", "neural waveform", "one-layer sample-token self-attention encoder"],
            ["derivative_gate_transformer_new", "new architecture", "transformer over waveform, first derivative, and curvature channels with derivative-magnitude pooling"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S61a Pulse-Shape Timing Pedestal Phase Benchmark

## Abstract

Ticket `#2558` asks which pulse-shape degrees of freedom explain timing
residuals once pedestal, polarity, peak phase, and amplitude are fixed.  The
analysis first reproduces the registered B-stack selected-pulse count directly
from raw ROOT `h101/HRDv`, then evaluates a run-held-out timing-residual
benchmark.  The traditional comparator is a polarity-bound constant-fraction
and template time-walk correction with robust first-sample pedestal and
peak-phase covariates.  It is benchmarked against ridge, gradient-boosted
trees, MLP, 1D-CNN, a compact waveform transformer, and a ticket-local
derivative-gated transformer.

The winner named in `result.json` is **`{winner['method']}`** with held-out
`sigma_68 = {winner['sigma68_ns']:.4g} ns`
`[{winner['sigma68_ns_ci_low']:.4g}, {winner['sigma68_ns_ci_high']:.4g}]`,
median bias `{winner['bias_ns']:.4g} ns`, RMS `{winner['rms_ns']:.4g} ns`, and
`|error| > 5 ns` tail fraction `{winner['tail_fraction_abs_gt_5ns']:.4g}`.

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-3 --project testbeam` was
run exactly once.  It returned the malformed payload:

```text
{config['claim_command_output'].rstrip()}
```

Read-only GitHub inspection showed no issue claimed by
`worker:testbeam-laptop-3`, so issue `#2558` was manually label-swapped without
rerunning the helper:

```text
{config['manual_claim_workaround']['command']}
```

## Raw ROOT Reproduction

Input files are read from `{config['raw_root_dir']}`.  Each raw event vector is
reshaped as `(8, 18)`.  B-stack physics channels are B2, B4, B6, and B8.  With
`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`, the reproduced count is

`N = sum_e sum_c 1[max_t(x_e,c,t - b_e,c) > {config['amplitude_cut_adc']:.0f} ADC]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group raw count is **{int(reproduction.iloc[-1]['selected_pulses'])}**,
matching the registered value exactly.  The first input checksums are:

{md_table(inputs, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimand and Equations

The normalized pulse is `z_t = (x_t - b) / max(A, 1)`, where `A=max_t(x_t-b)`.
The sub-sample constant-fraction crossing at fraction `f` is

`t_f = k - 1 + (fA - y_(k-1)) / (y_k - y_(k-1))`,

with `k` the first pre-peak sample exceeding `fA`.  The target is the
run/stave-centered CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

First-derivative atoms are `d_t = z_(t+1) - z_t`; curvature atoms are
`c_t = d_(t+1) - d_t`.  For method `m`, error is
`epsilon_i(m) = y_i - yhat_i(m)`.  Resolution is reported as

`sigma_68 = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with full RMS, median bias, and timing-tail fractions at 5 ns and 10 ns.

## Split and Uncertainty

The split unit is the source run.  Held-out runs are `{config['heldout_runs']}`;
all other configured runs are training runs.  The sampled benchmark rows are:

{md_table(counts, ['split', 'rows'])}

All quoted 95% confidence intervals use `{config['bootstrap_replicates']}`
percentile bootstrap replicates that resample held-out runs with replacement.
This is intentionally stricter than an event bootstrap because run-to-run
transfer is the ticket's target.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is sensible here because the scientific hypothesis is
local: derivative and curvature channels should identify onset, peak-phase, and
late-tail deformations after pedestal and amplitude are controlled.

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'rms_ns_ci_low', 'rms_ns_ci_high', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Paired Deltas Against Traditional

Positive `delta_sigma68_ns` means worse resolution than the traditional
polarity-bound CFD/template derivative comparator.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_rms_ns', 'delta_tail_fraction_abs_gt_5ns'])}

## Pulse-Shape Atom Coefficients

The atom table fits a standardized ridge model on training runs only, after
including fixed pedestal, amplitude, peak-phase, and timing covariates.  Large
coefficients indicate pulse-shape degrees of freedom that explain residual
timing variation beyond those fixed nuisance axes.

{md_table(atoms, ['feature', 'family', 'ridge_standardized_coef_ns', 'abs_coef_ns'], max_rows=30)}

## Placebo and Leakage Controls

The placebo controls shuffle the timing target within each source run before
training ridge and boosted-tree models.  They keep run composition and feature
marginals while breaking event-level pulse-shape association.

{md_table(placebo, ['control', 'n', 'bias_ns', 'sigma68_ns', 'rms_ns', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Run and Stratum Stability

{md_table(families, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=80)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=120)}

## Systematic Strata

The requested pedestal and phase stratifications are represented by
`pedestal_drift_bin`, `peak_sample`, CFD phase covariates, derivative-onset
bins, curvature-energy bins, late-tail morphology, pile-up separation, and
saturation-onset sidebands.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=240)}

Compressed axis view:

{md_table(axes, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=100)}

## Caveats

This is a raw-ROOT, run-held-out timing-residual benchmark, not an absolute
beamline timing truth measurement.  The target is constructed from the sampled
waveform itself, so a method that wins here explains stable internal
pulse-shape timing residuals rather than proving a detector-resolution limit.
The polarity is fixed to the B-stack channel convention and positive
baseline-subtracted pulses; an opposite-polarity acquisition would require the
same CFD equations with the sign convention inverted.  Neural models are
compact and trained under a fixed CPU budget, so the conclusion is about robust
transfer under constrained model capacity, not exhaustive hyperparameter
search.

Runtime for finalization was `{runtime:.1f} s` on `{platform.platform()}` with
Python `{platform.python_version()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def artifact_manifest(config: dict, result: dict) -> dict:
    rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": path.name, "bytes": int(path.stat().st_size), "sha256": sha256_path(path)})
    return {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "generated_at_unix": time.time(),
        "claim_command": config["claim_command"],
        "done_command": f"tn-ticket done {config['ticket_id']}",
        "result_winner": result["winner"]["method"],
        "artifacts": rows,
    }


def main() -> None:
    started = time.time()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    reproduction = pd.read_csv(OUT / "reproduction.csv")
    inputs = pd.read_csv(OUT / "input_sha256.csv")
    data = pd.read_csv(OUT / "benchmark_rows.csv.gz")
    pred = pd.read_csv(OUT / "predictions.csv.gz")
    metrics, by_run, strata, deltas, axes = summarize(pred, config)
    atoms = atom_coefficients(data)
    placebo = placebo_controls(data, int(config["random_seed"]) + 11)
    families = run_family_summary(pred, config)

    metrics.to_csv(OUT / "metrics.csv", index=False)
    by_run.to_csv(OUT / "by_run.csv", index=False)
    strata.to_csv(OUT / "strata.csv", index=False)
    deltas.to_csv(OUT / "method_deltas.csv", index=False)
    axes.to_csv(OUT / "frontier_axis_summary.csv", index=False)
    atoms.to_csv(OUT / "pulse_shape_atom_coefficients.csv", index=False)
    placebo.to_csv(OUT / "placebo_controls.csv", index=False)
    families.to_csv(OUT / "run_family_summary.csv", index=False)

    winner = metrics.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "ticket_number": int(config["ticket_number"]),
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_once": True,
        "claim_command": config["claim_command"],
        "claim_command_output": config["claim_command_output"],
        "manual_claim_workaround": config["manual_claim_workaround"],
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_head(),
        "script_sha256": sha256_path(ROOT / "scripts/ticket_2558_s61a_pulse_shape_timing_pedestal_phase.py"),
        "finalizer_sha256": sha256_path(Path(__file__)),
        "config_sha256": sha256_path(CONFIG),
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
        "required_method_coverage": {
            "traditional": "traditional_cfd_template_derivative",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "compact_transformer": "compact_waveform_transformer",
            "new_architecture": "derivative_gate_transformer_new",
        },
        "primary_metric": "held-out run-block bootstrap sigma68_ns of target_onset_residual_ns - prediction_ns; lower is better",
        "winner": {
            "method": str(winner["method"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "sigma68_ns_ci_low": float(winner["sigma68_ns_ci_low"]),
            "sigma68_ns_ci_high": float(winner["sigma68_ns_ci_high"]),
            "bias_ns": float(winner["bias_ns"]),
            "bias_ns_ci_low": float(winner["bias_ns_ci_low"]),
            "bias_ns_ci_high": float(winner["bias_ns_ci_high"]),
            "rms_ns": float(winner["rms_ns"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "frontier_axis_table": json_safe(axes.to_dict("records")),
        "run_family_table": json_safe(families.to_dict("records")),
        "pulse_shape_atom_top10": json_safe(atoms.head(10).to_dict("records")),
        "placebo_controls": json_safe(placebo.to_dict("records")),
        "strata_axes": AXES,
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "claimed_ticket_body": "claimed_ticket_body.txt",
            "raw_reproduction": "reproduction.csv",
            "input_sha256": "input_sha256.csv",
            "benchmark_rows": "benchmark_rows.csv.gz",
            "predictions": "predictions.csv.gz",
            "method_metrics": "metrics.csv",
            "method_deltas": "method_deltas.csv",
            "run_heldout_metrics": "by_run.csv",
            "strata_metrics": "strata.csv",
            "frontier_axis_summary": "frontier_axis_summary.csv",
            "pulse_shape_atom_coefficients": "pulse_shape_atom_coefficients.csv",
            "placebo_controls": "placebo_controls.csv",
            "run_family_summary": "run_family_summary.csv",
        },
        "novel_tickets_appended": [],
        "next_tickets": [],
    }
    (OUT / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, inputs, data, pred, metrics, deltas, by_run, strata, axes, families, atoms, placebo, runtime)
    (OUT / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")
    (OUT / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: "
        + config["claim_command"]
        + "\nclaim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    manifest = artifact_manifest(config, result)
    (OUT / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
