#!/usr/bin/env python3
"""S41a frequency-domain pulse-shape timing transfer benchmark."""

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
CONFIG = ROOT / "configs/s41a_1784180497_766_02892549_frequency_domain_pulse_shape_timing_transfer.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

METHOD_ORDER = [
    "traditional_fft_template_cfd_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "lightweight_transformer",
    "spectrogram_patch_transformer_new",
]

AXES = [
    "pulse_shape_class",
    "pedestal_drift_bin",
    "pileup_separation_bin",
    "saturation_onset_bin",
    "energy_bin",
    "pid_sideband",
    "spectral_centroid_bin",
    "phase_slope_bin",
]

SPECTRAL_COLUMNS = (
    [f"fft_mag_{i:02d}" for i in range(1, 10)]
    + [f"fft_phase_{i:02d}" for i in range(1, 10)]
    + [
        "spectral_centroid",
        "spectral_entropy",
        "high_frequency_fraction",
        "dominant_frequency_bin",
        "phase_slope",
        "low_band_power",
        "mid_band_power",
        "high_band_power",
    ]
)


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s41a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.METHOD_ORDER = METHOD_ORDER
    original_feature_columns = module.feature_columns

    def feature_columns_with_fft(df: pd.DataFrame) -> list[str]:
        cols = original_feature_columns(df)
        return cols + [c for c in SPECTRAL_COLUMNS if c in df.columns]

    module.feature_columns = feature_columns_with_fft
    return module


def add_frequency_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add FFT descriptors to the 18-sample normalized waveform window."""
    waves = df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=float)
    tapered = waves * np.hanning(waves.shape[1])[None, :]
    fft = np.fft.rfft(tapered, axis=1)
    mag = np.abs(fft)
    phase = np.unwrap(np.angle(fft), axis=1)
    freq = np.arange(mag.shape[1], dtype=float)
    power = mag[:, 1:] ** 2
    power_sum = np.maximum(power.sum(axis=1), 1e-12)
    for i in range(1, mag.shape[1]):
        df[f"fft_mag_{i:02d}"] = np.log1p(mag[:, i])
        df[f"fft_phase_{i:02d}"] = phase[:, i]
    df["spectral_centroid"] = (mag[:, 1:] * freq[1:][None, :]).sum(axis=1) / np.maximum(mag[:, 1:].sum(axis=1), 1e-12)
    prob = power / power_sum[:, None]
    df["spectral_entropy"] = -(prob * np.log(np.maximum(prob, 1e-12))).sum(axis=1) / np.log(prob.shape[1])
    df["low_band_power"] = power[:, :2].sum(axis=1) / power_sum
    df["mid_band_power"] = power[:, 2:5].sum(axis=1) / power_sum
    df["high_band_power"] = power[:, 5:].sum(axis=1) / power_sum
    df["high_frequency_fraction"] = df["high_band_power"]
    df["dominant_frequency_bin"] = np.argmax(power, axis=1) + 1
    idx = np.arange(1, mag.shape[1], dtype=float)
    idx_centered = idx - idx.mean()
    phase_centered = phase[:, 1:] - phase[:, 1:].mean(axis=1, keepdims=True)
    df["phase_slope"] = (phase_centered * idx_centered[None, :]).sum(axis=1) / np.sum(idx_centered**2)
    df["spectral_centroid_bin"] = pd.qcut(
        df["spectral_centroid"], q=3, labels=["low", "mid", "high"], duplicates="drop"
    ).astype(str)
    df["phase_slope_bin"] = pd.qcut(
        df["phase_slope"], q=3, labels=["negative", "central", "positive"], duplicates="drop"
    ).astype(str)
    return df


def traditional_fft_prediction(df: pd.DataFrame, base) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    pred = base.traditional_prediction(df)
    residual = y[train] - pred[train]
    cols = [
        "spectral_centroid",
        "spectral_entropy",
        "high_frequency_fraction",
        "phase_slope",
        "low_band_power",
        "mid_band_power",
        "high_band_power",
    ]
    x_train = df.loc[train, cols].to_numpy(float)
    x_all = df[cols].to_numpy(float)
    mu = x_train.mean(axis=0)
    sig = x_train.std(axis=0) + 1e-9
    design = np.c_[np.ones(len(x_train)), (x_train - mu) / sig]
    coef = np.linalg.solve(design.T @ design + np.diag([0.0] + [2.0] * len(cols)), design.T @ residual)
    return pred + np.c_[np.ones(len(x_all)), (x_all - mu) / sig] @ coef


def phase_randomization_ablation(data: pd.DataFrame, base, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    train = data["split"].eq("train").to_numpy()
    y = data["target_onset_residual_ns"].to_numpy(float)
    feature_sets = {
        "full_spectral_gradient_boosted_trees": base.feature_columns(data),
        "pretrigger_only": ["baseline", "pretrigger_slope", "w00", "w01", "w02", "w03"],
        "amplitude_normalized_spectra_only": [c for c in SPECTRAL_COLUMNS if c in data.columns and not c.startswith("fft_phase")],
        "phase_randomized_spectra": [
            c
            for c in base.feature_columns(data)
            if c not in {f"fft_phase_{i:02d}" for i in range(1, 10)} | {"phase_slope"}
        ],
        "time_domain_no_fft": [c for c in base.feature_columns(data) if c not in SPECTRAL_COLUMNS],
    }
    for name, cols in feature_sets.items():
        model = base.HistGradientBoostingRegressor(max_iter=140, learning_rate=0.05, l2_regularization=0.02, random_state=117)
        x = data[cols].to_numpy(dtype=float)
        model.fit(x[train], y[train])
        pred = model.predict(x)
        frame = data[["run", "split", "target_onset_residual_ns"]].copy()
        frame["error_ns"] = frame["target_onset_residual_ns"] - pred
        held = frame[frame["split"].eq("heldout")]
        vals = base.metric_values(held)
        runs = sorted(held["run"].unique())
        boot = []
        for _ in range(200):
            take = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
            boot.append(base.metric_values(sample)["sigma68_ns"])
        rows.append(
            {
                "ablation": name,
                "n_features": int(len(cols)),
                "sigma68_ns": vals["sigma68_ns"],
                "sigma68_ns_ci_low": float(np.percentile(boot, 2.5)),
                "sigma68_ns_ci_high": float(np.percentile(boot, 97.5)),
                "tail_fraction_abs_gt_5ns": vals["tail_fraction_abs_gt_5ns"],
            }
        )
    out = pd.DataFrame(rows).sort_values("sigma68_ns").reset_index(drop=True)
    base_value = float(out.loc[out["ablation"].eq("full_spectral_gradient_boosted_trees"), "sigma68_ns"].iloc[0])
    out["delta_sigma68_vs_full_ns"] = out["sigma68_ns"] - base_value
    return out


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


def artifact_manifest(out: Path, config: dict, result: dict) -> dict:
    rows = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append(
                {
                    "path": path.name,
                    "bytes": int(path.stat().st_size),
                    "sha256": sha256_path(path),
                }
            )
    return {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "generated_at_unix": time.time(),
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
        "done_command": f"tn-ticket done {config['ticket_id']} --project testbeam",
        "result_winner": result["winner"]["method"],
        "artifacts": rows,
    }


def sha256_path(path: Path, block_size: int = 1024 * 1024) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


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


def append_frequency_strata(strata: pd.DataFrame, predictions: pd.DataFrame, base) -> pd.DataFrame:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method", observed=False):
        for col in ["spectral_centroid_bin", "phase_slope_bin"]:
            for level, sg in group.groupby(col, observed=False):
                rows.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **base.metric_values(sg)})
    if rows:
        strata = pd.concat([strata, pd.DataFrame(rows)], ignore_index=True)
    return strata.sort_values(["stratum", "level", "method"]).reset_index(drop=True)


def summarize_s41a(predictions: pd.DataFrame, config: dict, rng: np.random.Generator, base) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    metric_rows = []
    run_rows = []
    strata_rows = []
    boot_by_method: dict[str, dict[str, list[float]]] = {}
    strata_cols = [
        "pedestal_drift_bin",
        "pulse_shape_class",
        "pileup_separation_bin",
        "saturation_onset_bin",
        "energy_bin",
        "pid_sideband",
        "spectral_centroid_bin",
        "phase_slope_bin",
    ]
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "n": int(len(group)), **base.metric_values(group)}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = base.metric_values(boot)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples[key].append(value)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        boot_by_method[str(method)] = samples
        metric_rows.append(row)
        for run, rg in group.groupby("run", observed=False):
            run_rows.append({"method": method, "run": int(run), "n": int(len(rg)), **base.metric_values(rg)})
        for col in strata_cols:
            for level, sg in group.groupby(col, observed=False):
                strata_rows.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **base.metric_values(sg)})
    metrics = pd.DataFrame(metric_rows)
    metrics["method"] = pd.Categorical(metrics["method"], METHOD_ORDER, ordered=True)
    metrics = metrics.sort_values("sigma68_ns").reset_index(drop=True)
    delta_rows = []
    reference = "traditional_fft_template_cfd_timewalk"
    for method in metrics["method"].astype(str):
        if method == reference:
            continue
        row = {"method": method, "reference_method": reference}
        for key in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]:
            val = float(metrics.loc[metrics["method"].astype(str).eq(method), key].iloc[0])
            ref = float(metrics.loc[metrics["method"].astype(str).eq(reference), key].iloc[0])
            paired = np.asarray(boot_by_method[method][key]) - np.asarray(boot_by_method[reference][key])
            row[f"delta_{key}"] = val - ref
            row[f"delta_{key}_ci_low"] = float(np.percentile(paired, 2.5))
            row[f"delta_{key}_ci_high"] = float(np.percentile(paired, 97.5))
        delta_rows.append(row)
    return (
        metrics,
        pd.DataFrame(run_rows).sort_values(["method", "run"]),
        pd.DataFrame(strata_rows).sort_values(["stratum", "level", "method"]),
        pd.DataFrame(delta_rows).sort_values("delta_sigma68_ns"),
    )


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
    trad = metrics[metrics["method"].astype(str).eq("traditional_fft_template_cfd_timewalk")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_fft_template_cfd_timewalk", "traditional", "CFD50 residual plus monotone log-amplitude time-walk, CFD20/50 template-shape correction, and linear FFT band/phase residual correction"],
            ["ridge", "linear ML", "standardized ridge regression on pedestal, amplitude, CFD, tail, pile-up, saturation, waveform samples, and FFT descriptors"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same leakage-controlled time/frequency feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform, detector-state, and spectral summaries"],
            ["1d_cnn", "neural waveform", "compact convolutional regressor over the normalized 18-sample waveform window"],
            ["lightweight_transformer", "neural waveform", "one-layer sample-attention encoder with position input and amplitude-weighted pooling"],
            ["spectrogram_patch_transformer_new", "new architecture", "ticket-local spectrogram/patch proxy: gated convolutional encoder trained on waveform patches while FFT descriptors enter the tabular heads"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S41a Frequency-Domain Pulse-Shape Timing Transfer Benchmark

## Abstract

Ticket `{config['ticket_id']}` asks whether frequency-domain pulse-shape
descriptors improve timing transfer across run, rate, and sensor conditions
without leaking pedestal or amplitude state.  This study rebuilds the registered
B-stack selected-pulse count directly from raw ROOT files, constructs a
run-held-out timing residual benchmark from the same waveforms, and compares a
strong FFT/template/CFD baseline with ridge, gradient-boosted trees, MLP,
1D-CNN, a lightweight transformer, and a new spectrogram/patch transformer proxy.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`{winner}`** as the
winner: `sigma_68 = {best['sigma68_ns']:.4g} ns`
`[{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.  The
traditional FFT/CFD/template reference obtains `{trad['sigma68_ns']:.4g} ns`
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

## Estimand, Spectral Features, and Equations

Constant-fraction time at fraction `f` is the pre-peak linear interpolation

`t_f = k - 1 + (f A - y_{{k-1}}) / (y_k - y_{{k-1}})`,

where `y_t = x_t - b`, `y_{{k-1}} < fA <= y_k`, and the crossing index `k`
cannot exceed the waveform peak.  The prediction target is a run/stave-centered
CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

For method `m`, `epsilon_i^m = y_i - hat y_i^m`.  The resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with signed bias `median(epsilon)`.  The normalized waveform
`z_t = (x_t - b) / max(A, 1)` is Hann tapered before the real FFT

`Z_k = sum_t h_t z_t exp(-2 pi i k t / 18)`.

The spectral feature set contains `log(1 + |Z_k|)`, unwrapped phase
`arg(Z_k)`, band powers, spectral entropy

`H = - sum_k p_k log(p_k) / log(K)`,

and centroid

`C = sum_k k |Z_k| / sum_k |Z_k|`.

The traditional comparator is

`hat y_trad = r_50 + g(log(1 + A)) + alpha + beta (t_0.50 - t_0.20) + gamma^T s`,

where `r_50` is the run/stave-centered CFD50 residual, `g` is a non-increasing
isotonic time-walk correction fitted on training runs, and `s` is the
standardized FFT band/phase summary vector.  The ridge penalty on `gamma`
prevents the frequency correction from silently absorbing run identifiers.

## Split, Uncertainty, and Leakage Controls

The split unit is the run.  Held-out runs are `{config['heldout_runs']}`; all
other configured B-stack runs train the models.  The sampled benchmark rows are:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` percentile
bootstrap replicates that resample held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

No model receives run number, event number, or split indicator.  Pedestal
wander, amplitude state, and pulse-shape changes enter only through waveform
quantities: baseline displacement, pretrigger slope, normalized samples, tail
fraction, late prominence, flat-top occupancy, and FFT descriptors computed
after amplitude normalization.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The lightweight transformer is included because sample attention can express
sub-window alignment without hand-specifying an onset index.  The
`spectrogram_patch_transformer_new` architecture is the ticket-specific new
model: a spectrogram/patch proxy using a gated convolutional waveform encoder
while frequency-domain patch descriptors enter the tabular heads.  This is
sensible for S41a because the ticket is explicitly about whether spectral shape
axes add transfer information beyond CFD timing and amplitude.

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Paired Deltas Against FFT/CFD Template

Positive `delta_sigma68_ns` means the learned method is wider than the
traditional FFT/CFD template reference under matched held-out run-block
bootstrap.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns'])}

## Run-Split Stability

{md_table(families, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=60)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=90)}

## Pedestal and Pulse-Shape Stress Tables

Stress axes are raw-waveform proxies: pedestal drift is absolute baseline
displacement from the run/stave median; pulse-shape class is late-tail fraction;
pile-up proximity is late secondary prominence spacing; saturation onset is
high amplitude or flat-top occupancy; energy proxy is amplitude quartile; PID
sideband is duplicate-readout amplitude ratio; spectral centroid and phase
slope are frequency-domain stability axes.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=180)}

Axis-compressed view:

{md_table(axes, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=80)}

## Systematic Ablations

The ablations use the gradient-boosted-tree learner and remove or isolate
feature families to test whether learned timing is mostly pretrigger leakage,
amplitude-normalized spectra, phase information, or ordinary time-domain
interpolation.

{md_table(ablations, ['ablation', 'n_features', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Interpretation, Systematics, and Caveats

This is a comparative frequency-domain alignment benchmark, not an external timing-truth
measurement.  The ROOT tree provides digitized waveforms but not independent
particle truth, electronics-state labels, or picosecond reference timing.
Therefore, the analysis supports claims about relative method behavior on a
reproducible waveform-derived residual, not absolute beamline timing.

The run-block bootstrap targets transfer across data-taking periods and can be
wider than event-level uncertainty.  Small strata, especially close pile-up and
near-saturation levels, must be interpreted with their row counts.  Neural
models are compact and trained on a fixed small epoch budget; this tests whether
frequency-domain descriptors naturally beat a strong FFT/CFD/template
construction under run transfer, not whether exhaustive neural architecture
search can eventually overfit this proxy target.

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
    (out / "claimed_ticket.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    input_hashes = input_sha256_table(config, base)
    input_hashes.to_csv(out / "input_sha256.csv", index=False)

    data = add_frequency_features(base.sample_pulses(config, rng))
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)

    preds = {"traditional_fft_template_cfd_timewalk": traditional_fft_prediction(data, base)}
    preds.update(base.fit_tabular_methods(data))
    preds["1d_cnn"] = base.fit_cnn(data, config, "1d_cnn", gated=False, seed=int(config["random_seed"]) + 1)
    preds["lightweight_transformer"] = base.fit_transformer(data, config, seed=int(config["random_seed"]) + 3)
    preds["spectrogram_patch_transformer_new"] = base.fit_cnn(data, config, "spectrogram_patch_transformer_new", gated=True, seed=int(config["random_seed"]) + 2)

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
        "spectral_centroid_bin",
        "phase_slope_bin",
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

    metrics, by_run, strata, deltas = summarize_s41a(predictions, config, rng, base)
    axes = axis_summary(strata)
    families = run_family_summary(predictions, config, base)
    ablations = phase_randomization_ablation(data, base, rng)

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
        "claimed_ticket_text": config["claimed_ticket_text"],
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
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
            "event_predictions": "predictions.csv.gz",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, base, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, result, runtime)
    (out / "manifest.json").write_text(json.dumps(artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
