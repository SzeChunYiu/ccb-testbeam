#!/usr/bin/env python3
"""S47c pedestal-memory transfer map benchmark."""

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
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s47c_2437_pedestal_memory_transfer_map.json"
S51A_SCRIPT = ROOT / "scripts/s51a_2454_waveform_shape_time_identifiability_atlas.py"

METHOD_ORDER = [
    "traditional_median_template_cfd_timewalk_shape",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_waveform_transformer",
    "pedestal_memory_fusion_cnn_new",
]

PEDESTAL_COLUMNS = [
    "baseline_centered",
    "baseline_lag1",
    "baseline_ewm5",
    "baseline_innovation",
    "baseline_ar1_proxy",
    "baseline_run_z",
    "baseline_abs_change",
    "pedestal_memory_score",
]

AXES = [
    "pedestal_drift_bin",
    "pedestal_memory_bin",
    "baseline_innovation_bin",
    "energy_bin",
    "peak_phase_bin",
    "pulse_shape_class",
    "q_template_error_bin",
    "derivative_onset_bin",
    "curvature_energy_bin",
    "late_tail_morphology",
    "pileup_separation_bin",
    "saturation_onset_bin",
    "pid_sideband",
]


def load_s51a():
    spec = importlib.util.spec_from_file_location("s51a_for_s47c", S51A_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S51A_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.METHOD_ORDER = METHOD_ORDER
    module.AXES = AXES
    base = module.load_base()
    original_feature_columns = base.feature_columns

    def feature_columns_with_pedestal_memory(df: pd.DataFrame) -> list[str]:
        cols = original_feature_columns(df)
        for col in PEDESTAL_COLUMNS:
            if col in df.columns and col not in cols:
                cols.append(col)
        return cols

    base.feature_columns = feature_columns_with_pedestal_memory
    return module, base


def add_pedestal_memory_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["run", "stave", "event"]).reset_index(drop=True)
    group = df.groupby(["run", "stave"], observed=False)
    run_median = group["baseline"].transform("median")
    run_std = group["baseline"].transform("std").replace(0.0, np.nan).fillna(1.0)
    df["baseline_centered"] = df["baseline"] - run_median
    df["baseline_run_z"] = df["baseline_centered"] / run_std
    df["baseline_lag1"] = group["baseline_centered"].shift(1).fillna(0.0)
    df["baseline_ewm5"] = group["baseline_centered"].transform(lambda s: s.shift(1).ewm(span=5, adjust=False).mean()).fillna(0.0)
    df["baseline_innovation"] = df["baseline_centered"] - df["baseline_ewm5"]
    df["baseline_abs_change"] = (df["baseline_centered"] - df["baseline_lag1"]).abs()
    lag = df["baseline_lag1"].to_numpy(float)
    cur = df["baseline_centered"].to_numpy(float)
    denom = np.maximum(np.abs(lag), 1.0)
    df["baseline_ar1_proxy"] = cur / denom
    score_terms = np.column_stack(
        [
            np.abs(df["baseline_run_z"].to_numpy(float)),
            np.abs(df["baseline_innovation"].to_numpy(float)) / (run_std.to_numpy(float) + 1e-9),
            df["baseline_abs_change"].to_numpy(float) / (run_std.to_numpy(float) + 1e-9),
        ]
    )
    df["pedestal_memory_score"] = np.nanmean(score_terms, axis=1)
    df["pedestal_memory_bin"] = pd.qcut(
        df["pedestal_memory_score"], q=3, labels=["quiet_memory", "moderate_memory", "strong_memory"], duplicates="drop"
    ).astype(str)
    df["baseline_innovation_bin"] = pd.qcut(
        df["baseline_innovation"].abs(), q=3, labels=["low_innovation", "mid_innovation", "high_innovation"], duplicates="drop"
    ).astype(str)
    return df


def traditional_pedestal_memory_prediction(df: pd.DataFrame, s51a, base) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    pred = s51a.traditional_derivative_prediction(df, base)
    residual = y[train] - pred[train]
    cols = [c for c in PEDESTAL_COLUMNS if c in df.columns] + [
        "amplitude",
        "rise_time_sample",
        "tail_fraction",
        "pretrigger_slope",
    ]
    x_train = df.loc[train, cols].to_numpy(float)
    x_all = df.loc[:, cols].to_numpy(float)
    mu = x_train.mean(axis=0)
    sig = x_train.std(axis=0) + 1e-9
    design = np.c_[np.ones(len(x_train)), (x_train - mu) / sig]
    penalty = np.diag([0.0] + [5.0] * len(cols))
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ residual)
    return pred + np.c_[np.ones(len(x_all)), (x_all - mu) / sig] @ coef


def fit_pedestal_memory_fusion_cnn(df: pd.DataFrame, config: dict, seed: int) -> np.ndarray:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("torch is required for pedestal_memory_fusion_cnn_new") from exc

    class PedestalFusionCNN(nn.Module):
        def __init__(self, n_aux: int) -> None:
            super().__init__()
            self.wave = nn.Sequential(
                nn.Conv1d(3, 18, 3, padding=1),
                nn.GELU(),
                nn.Conv1d(18, 18, 3, padding=1),
                nn.GELU(),
            )
            self.aux = nn.Sequential(nn.Linear(n_aux, 16), nn.GELU(), nn.Linear(16, 18), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(18 * 18 + n_aux, 48), nn.GELU(), nn.Linear(48, 1))

        def forward(self, wave: "torch.Tensor", aux: "torch.Tensor") -> "torch.Tensor":
            h = self.wave(wave)
            gate = self.aux(aux).unsqueeze(-1)
            h = h * (1.0 + gate)
            return self.head(torch.cat([h.flatten(1), aux], dim=1)).squeeze(-1)

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    waves = df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    d1 = np.pad(np.diff(waves, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    d2 = np.pad(np.diff(d1, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    xw = np.stack([waves, d1, d2], axis=1)
    aux_cols = [c for c in PEDESTAL_COLUMNS if c in df.columns] + ["amplitude", "tail_fraction", "rise_time_sample"]
    aux = df[aux_cols].to_numpy(dtype=np.float32)
    train = df["split"].eq("train").to_numpy()
    aux_mu = aux[train].mean(axis=0)
    aux_sd = aux[train].std(axis=0) + 1e-6
    aux = ((aux - aux_mu) / aux_sd).astype(np.float32)
    y = df["target_onset_residual_ns"].to_numpy(dtype=np.float32)
    ym = float(y[train].mean())
    ys = float(y[train].std() + 1e-6)
    ds = TensorDataset(
        torch.from_numpy(xw[train]),
        torch.from_numpy(aux[train]),
        torch.from_numpy(((y[train] - ym) / ys).astype(np.float32)),
    )
    loader = DataLoader(
        ds,
        batch_size=int(config["nn"]["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = PedestalFusionCNN(aux.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["nn"]["epochs"])):
        for xb, xa, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb, xa), yb)
            loss.backward()
            opt.step()
    out = []
    model.eval()
    with torch.no_grad():
        tw = torch.from_numpy(xw)
        ta = torch.from_numpy(aux)
        for start in range(0, len(tw), 2048):
            out.append(model(tw[start : start + 2048], ta[start : start + 2048]).cpu().numpy())
    return np.concatenate(out) * ys + ym


def pedestal_systematics(predictions: pd.DataFrame, base) -> pd.DataFrame:
    rows = []
    held = predictions[predictions["split"].eq("heldout")]
    for (method, level), group in held.groupby(["method", "pedestal_memory_bin"], observed=False):
        vals = base.metric_values(group)
        rows.append(
            {
                "method": str(method),
                "pedestal_memory_bin": str(level),
                "n": int(len(group)),
                **vals,
                "median_energy_proxy_adc": float(group["amplitude"].median()),
                "pid_high_duplicate_fraction": float((group["pid_sideband"] == "high_duplicate").mean()),
                "near_saturation_fraction": float((group["saturation_onset_bin"] == "near_saturation").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["pedestal_memory_bin", "sigma68_ns"])


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, [c for c in columns if c in df.columns]].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("|", "\\|") for col in view.columns) + " |")
    return "\n".join(lines)


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


def write_report(config, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, ped_syst, result, runtime) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    trad = metrics[metrics["method"].astype(str).eq("traditional_median_template_cfd_timewalk_shape")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_median_template_cfd_timewalk_shape", "traditional", "CFD/template derivative timing plus ridge-regularized AR(1), rolling-baseline, and innovation residual correction"],
            ["ridge", "linear ML", "standardized ridge on waveform, derivative, curvature, pedestal-memory, energy-proxy, and PID-sideband features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted trees on the same leakage-controlled feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform and pedestal-state summaries"],
            ["1d_cnn", "neural waveform", "compact convolution over the 18 normalized waveform samples"],
            ["compact_waveform_transformer", "neural waveform", "one-layer sample self-attention encoder"],
            ["pedestal_memory_fusion_cnn_new", "new architecture", "CNN over waveform, derivative, and curvature channels gated by event-ordered pedestal-memory covariates"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S47c Pedestal-Memory Transfer Map for Energy Timing and PID

## Abstract

Ticket `{config['ticket_id']}` asked for an academic-grade map from pedestal drift
and baseline memory into pulse-shape descriptors, timing residuals, pile-up
tagging, saturation recovery, energy scale, and PID stability across run
conditions.  The registered B-stack count is first reproduced directly from raw
ROOT `h101/HRDv`; the same pulses are then used for a run-held-out benchmark.
The winner named in `result.json` is **`{winner}`**, with held-out run-bootstrap
`sigma_68 = {best['sigma68_ns']:.4g} ns [{best['sigma68_ns_ci_low']:.4g},
{best['sigma68_ns_ci_high']:.4g}]`.  The strong traditional comparator obtains
`{trad['sigma68_ns']:.4g} ns [{trad['sigma68_ns_ci_low']:.4g},
{trad['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

The raw number is reproduced from `{config['raw_root_dir']}`.  For each event,
`HRDv` is reshaped to `(8, 18)`.  For B-stack channel `c`, with
`b_c = median(x_c[0],...,x_c[3])`, the selected-pulse count is

`N = sum_e sum_c 1[max_t(x_e,c,t - b_e,c) > {config['amplitude_cut_adc']:.0f}]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
Input hashes are in `input_sha256.csv`; first rows:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimands and Equations

Constant-fraction time is linearly interpolated before the peak:

`t_f = k - 1 + (f A - y_(k-1))/(y_k - y_(k-1))`, where `y_t=x_t-b`.

The timing target is run/stave-centered CFD20 residual
`Y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.
Resolution is `sigma_68 = 0.5 [Q_84(epsilon)-Q_16(epsilon)]` for
`epsilon_i=Y_i-hat(Y_i)`.  Pedestal memory is represented by event-ordered
baseline covariates within each run/stave:

`m_i = alpha b'_(i-1) + (1-alpha) m_(i-1)`,
`u_i=b'_i-m_i`, and `rho_i=b'_i / max(|b'_(i-1)|,1)`,

where `b'_i = b_i - median(b | run, stave)`.  The traditional method adds
ridge-regularized terms in `(b'_i, b'_(i-1), m_i, u_i, rho_i)` to the existing
CFD/template derivative time-walk fit.  This is the registered strong
traditional pedestal-memory comparator.

Energy scale is a raw charge proxy, `A=max_t(y_t)`.  PID stability is the
duplicate-readout sideband proxy, `A_dup/A`, with low/high duplicate sidebands
treated as operating-point shifts rather than external truth labels.

## Split and Uncertainty

The split unit is the run.  Held-out runs are `{config['heldout_runs']}`; all
other configured runs train the models.  Benchmark rows:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` paired percentile
bootstrap replicates resampling held-out runs with replacement.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is sensible here because the ticket hypothesis is
pedestal-memory transfer, not generic waveform fitting.  The model gates
waveform/derivative/curvature convolution channels by baseline lag, rolling
memory, innovation, AR(1) proxy, and run-normalized pedestal displacement.

## Primary Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Paired Deltas Versus Traditional

Positive `delta_sigma68_ns` means worse timing resolution than the traditional
pedestal-memory fit.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns'])}

## Pedestal, Energy, and PID Transfer Systematics

{md_table(ped_syst, ['pedestal_memory_bin', 'method', 'n', 'bias_ns', 'sigma68_ns', 'median_energy_proxy_adc', 'pid_high_duplicate_fraction', 'near_saturation_fraction'], max_rows=80)}

## Run and Family Stability

{md_table(families, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=80)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=120)}

## Stratified Systematics

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=220)}

Compressed axis view:

{md_table(axes, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=120)}

## Ablations

{md_table(ablations, ['ablation', 'n_features', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Caveats

The raw files do not carry independent external particle-identification or
picosecond timing truth per pulse.  Timing, energy, saturation, and PID
statements are therefore transfer diagnostics on reproducible waveform-derived
proxies: CFD20 residual, raw amplitude, flat-top/late-pulse proxies, and
duplicate-readout sideband.  Run-block bootstrap protects against event-level
overconfidence but leaves model selection multiplicity as a caveat.  Neural
training used a fixed small CPU budget; the conclusion is about whether compact
learned models naturally beat a strong transparent pedestal-memory fit, not
about exhaustive architecture search.

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
    s51a, base = load_s51a()
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    (out / "claimed_ticket.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    input_hashes = s51a.input_sha256_table(config, base)
    input_hashes.to_csv(out / "input_sha256.csv", index=False)

    data = s51a.add_derivative_features(base.sample_pulses(config, rng))
    data = add_pedestal_memory_features(data)
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)

    preds = {"traditional_median_template_cfd_timewalk_shape": traditional_pedestal_memory_prediction(data, s51a, base)}
    preds.update(base.fit_tabular_methods(data))
    preds["1d_cnn"] = base.fit_cnn(data, config, "1d_cnn", gated=False, seed=int(config["random_seed"]) + 1)
    preds["compact_waveform_transformer"] = base.fit_transformer(data, config, seed=int(config["random_seed"]) + 2)
    preds["pedestal_memory_fusion_cnn_new"] = fit_pedestal_memory_fusion_cnn(data, config, seed=int(config["random_seed"]) + 3)

    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        "amplitude",
        "q_template_error",
        *AXES,
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

    metrics, by_run, strata, deltas = s51a.summarize_s51a(predictions, config, rng, base)
    axes = s51a.axis_summary(strata)
    families = s51a.run_family_summary(predictions, config, base)
    ablations = s51a.derivative_ablation_study(data, rng, base)
    ped_syst = pedestal_systematics(predictions, base)

    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    axes.to_csv(out / "frontier_axis_summary.csv", index=False)
    families.to_csv(out / "run_family_summary.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)
    ped_syst.to_csv(out / "pedestal_memory_systematics.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_ticket_text": config["claimed_ticket_text"],
        "claim_command_run_once": "tn-ticket claim testbeam-laptop-3 --project testbeam",
        "claim_command_returned_null": True,
        "manual_claim_recovery_issue": 2437,
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
            "calibration_slope": float(winner_row["calibration_slope"]),
            "q_template_mse": float(winner_row["q_template_mse"]),
            "failure_rate_abs_gt_5ns": float(winner_row["failure_rate_abs_gt_5ns"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "pedestal_memory_systematics": json_safe(ped_syst.to_dict("records")),
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
            "input_sha256": "input_sha256.csv",
            "pedestal_memory_systematics": "pedestal_memory_systematics.csv",
        },
        "novel_tickets_appended": [],
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, ped_syst, result, runtime)
    (out / "manifest.json").write_text(json.dumps(s51a.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out), "winner": result["winner"]}, indent=2))


if __name__ == "__main__":
    main()
