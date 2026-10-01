#!/usr/bin/env python3
"""S44a / issue #2414: guardrail-orthogonal S03 cross-sample timing audit."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s44a_2414_s03_guardrail_cross_sample_cnn_timewalk.json"
S43 = ROOT / "scripts/s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark.py"

METHOD_ORDER = [
    "analytic_s03_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn_waveform_only",
    "guardrail_orthogonal_edge_transformer_new",
]


def load_s43():
    spec = importlib.util.spec_from_file_location("s43_base_for_2414", S43)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S43}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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
    headers = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "\\|") for c in view.columns) + " |")
    return "\n".join(lines)


def feature_columns(df: pd.DataFrame, amplitude_tail_excluded: bool = False) -> list[str]:
    base = [
        "baseline",
        "peak_sample",
        "area",
        "positive_area",
        "pretrigger_slope",
        "cfd50_sample",
        "cfd80_sample",
        "rise_time_sample",
        "late_peak_sample",
        "pileup_separation_sample",
        "late_peak_prominence",
        "flat_top_samples",
        "max_rise_slope",
        "max_fall_slope",
        "onset_slope_sum",
        "late_slope_sum",
        "curvature_peak",
        "curvature_energy",
        "derivative_centroid",
        "curvature_centroid",
        "pretrigger_derivative_rms",
        "late_curvature_rms",
    ]
    wave = [f"w{i:02d}" for i in range(18)]
    deriv = [f"d1_{i:02d}" for i in range(17)] + [f"d2_{i:02d}" for i in range(16)]
    cols = base + wave + deriv
    if not amplitude_tail_excluded:
        cols = ["amplitude", "tail_fraction"] + cols
    else:
        banned = {"tail_fraction", "late_peak_sample", "late_peak_prominence", "late_slope_sum", "late_curvature_rms"}
        banned.update({f"w{i:02d}" for i in range(12, 18)})
        banned.update({f"d1_{i:02d}" for i in range(11, 17)})
        banned.update({f"d2_{i:02d}" for i in range(10, 16)})
        cols = [c for c in cols if c not in banned]
    return [c for c in cols if c in df.columns]


def apply_ticket_split(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    train_runs = {int(r) for r in config["train_runs"]}
    heldout_runs = {int(r) for r in config["heldout_runs"]}
    keep = df["run"].isin(train_runs | heldout_runs)
    out = df.loc[keep].copy()
    out["split"] = np.where(out["run"].isin(train_runs), "train", "heldout")
    train = out["split"].eq("train")
    qlo, qhi = [float(x) for x in config["support_quantiles"]]
    amp_lo, amp_hi = out.loc[train, "amplitude"].quantile([qlo, qhi])
    tail_lo, tail_hi = out.loc[train, "tail_fraction"].quantile([qlo, qhi])
    out["support_matched"] = (
        out["amplitude"].between(float(amp_lo), float(amp_hi))
        & out["tail_fraction"].between(float(tail_lo), float(tail_hi))
        & out["stave"].isin(out.loc[train, "stave"].unique())
    )
    out["evaluation_domain"] = np.where(out["support_matched"], "support_matched", "full_transfer")
    return out.reset_index(drop=True)


def fit_tabular(df: pd.DataFrame, amplitude_tail_excluded: bool) -> dict[str, np.ndarray]:
    x = df[feature_columns(df, amplitude_tail_excluded=amplitude_tail_excluded)].to_numpy(dtype=float)
    y = df["target_onset_residual_ns"].to_numpy(float)
    train = df["split"].eq("train").to_numpy()
    models = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=4.0)),
        "gradient_boosted_trees": HistGradientBoostingRegressor(
            max_iter=180, learning_rate=0.045, l2_regularization=0.04, random_state=2414
        ),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                alpha=1e-3,
                max_iter=40,
                random_state=2415,
                early_stopping=True,
            ),
        ),
    }
    out = {}
    for name, model in models.items():
        model.fit(x[train], y[train])
        out[name] = model.predict(x)
    return out


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    err = frame["error_ns"].to_numpy(float)
    err = err[np.isfinite(err)]
    if len(err) == 0:
        return {
            "bias_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "rms_ns": float("nan"),
            "tail_fraction_abs_gt_5ns": float("nan"),
            "tail_fraction_abs_gt_10ns": float("nan"),
        }
    centered = err - np.nanmedian(err)
    return {
        "bias_ns": float(np.nanmedian(err)),
        "sigma68_ns": float(0.5 * (np.nanpercentile(centered, 84) - np.nanpercentile(centered, 16))),
        "rms_ns": float(np.sqrt(np.nanmean(centered**2))),
        "tail_fraction_abs_gt_5ns": float((np.abs(err) > 5.0).mean()),
        "tail_fraction_abs_gt_10ns": float((np.abs(err) > 10.0).mean()),
    }


def summarize(predictions: pd.DataFrame, config: dict, rng: np.random.Generator, domain: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    if domain == "support_matched":
        held = held[held["support_matched"]].copy()
    metric_rows = []
    run_rows = []
    boot_by_method: dict[str, dict[str, list[float]]] = {}
    for method, group in held.groupby("method", observed=False):
        row = {"domain": domain, "method": str(method), "n": int(len(group)), **metric_values(group)}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = metric_values(boot)
            for key, val in vals.items():
                if np.isfinite(val):
                    samples[key].append(val)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        boot_by_method[str(method)] = samples
        metric_rows.append(row)
        for run, rg in group.groupby("run", observed=False):
            run_rows.append({"domain": domain, "method": str(method), "run": int(run), "n": int(len(rg)), **metric_values(rg)})
    metrics = pd.DataFrame(metric_rows).sort_values("sigma68_ns").reset_index(drop=True)
    reference = "analytic_s03_timewalk"
    delta_rows = []
    for method in metrics["method"].astype(str):
        if method == reference:
            continue
        row = {"domain": domain, "method": method, "reference_method": reference}
        for key in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]:
            val = float(metrics.loc[metrics["method"].eq(method), key].iloc[0])
            ref = float(metrics.loc[metrics["method"].eq(reference), key].iloc[0])
            paired = np.asarray(boot_by_method[method][key]) - np.asarray(boot_by_method[reference][key])
            row[f"delta_{key}"] = val - ref
            row[f"delta_{key}_ci_low"] = float(np.percentile(paired, 2.5))
            row[f"delta_{key}_ci_high"] = float(np.percentile(paired, 97.5))
        delta_rows.append(row)
    return metrics, pd.DataFrame(run_rows).sort_values(["method", "run"]), pd.DataFrame(delta_rows).sort_values("delta_sigma68_ns")


def strata_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method", observed=False):
        for col in ["support_matched", "energy_bin", "pulse_shape_class", "pedestal_drift_bin", "late_tail_morphology"]:
            for level, sg in group.groupby(col, observed=False):
                rows.append({"method": str(method), "stratum": col, "level": str(level), "n": int(len(sg)), **metric_values(sg)})
    return pd.DataFrame(rows).sort_values(["stratum", "level", "sigma68_ns"]).reset_index(drop=True)


def amplitude_tail_ablation(df: pd.DataFrame, predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    preds = fit_tabular(df, amplitude_tail_excluded=True)
    rows = []
    for method, pred in preds.items():
        frame = df[["run", "split", "target_onset_residual_ns", "support_matched"]].copy()
        frame["method"] = f"{method}_amplitude_tail_excluded"
        frame["prediction_ns"] = pred
        frame["error_ns"] = frame["target_onset_residual_ns"] - pred
        for domain in ["full_transfer", "support_matched"]:
            held = frame[frame["split"].eq("heldout")].copy()
            if domain == "support_matched":
                held = held[held["support_matched"]].copy()
            row = {"domain": domain, "method": frame["method"].iloc[0], "n": int(len(held)), **metric_values(held)}
            runs = sorted(held["run"].unique())
            samples = []
            for _ in range(int(config["bootstrap_replicates"])):
                take = rng.choice(runs, size=len(runs), replace=True)
                boot = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
                samples.append(metric_values(boot)["sigma68_ns"])
            row["sigma68_ns_ci_low"] = float(np.percentile(samples, 2.5))
            row["sigma68_ns_ci_high"] = float(np.percentile(samples, 97.5))
            row["variant"] = "amplitude_tail_excluded"
            rows.append(row)
    base = predictions[predictions["method"].isin(["ridge", "gradient_boosted_trees", "mlp"])].copy()
    for method, group in base.groupby("method", observed=False):
        for domain in ["full_transfer", "support_matched"]:
            held = group[group["split"].eq("heldout")].copy()
            if domain == "support_matched":
                held = held[held["support_matched"]].copy()
            rec = {"domain": domain, "method": str(method), "n": int(len(held)), **metric_values(held)}
            runs = sorted(held["run"].unique())
            samples = []
            for _ in range(int(config["bootstrap_replicates"])):
                take = rng.choice(runs, size=len(runs), replace=True)
                boot = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
                samples.append(metric_values(boot)["sigma68_ns"])
            rec["sigma68_ns_ci_low"] = float(np.percentile(samples, 2.5))
            rec["sigma68_ns_ci_high"] = float(np.percentile(samples, 97.5))
            rec["variant"] = "primary_features"
            rows.append(rec)
    return pd.DataFrame(rows).sort_values(["domain", "method"]).reset_index(drop=True)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append({"run": int(run), "path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)})
    return pd.DataFrame(rows)


def artifact_manifest(out: Path, config: dict, result: dict) -> dict:
    artifacts = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append({"path": path.name, "bytes": int(path.stat().st_size), "sha256": sha256_file(path)})
    return {
        "ticket_id": config["ticket_id"],
        "issue_number": 2414,
        "study_id": config["study_id"],
        "worker": config["worker"],
        "claim_command_invoked_once": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "manual_claim_recovery_note": "The command returned the documented null pseudo-ticket; issue #2414 was then label-swapped manually to factory:claimed + worker:testbeam-laptop-2.",
        "done_command": "tn-ticket done 2414",
        "winner": result["winner"]["method"],
        "artifacts": artifacts,
    }


def write_report(
    config: dict,
    reproduction: pd.DataFrame,
    input_hashes: pd.DataFrame,
    data: pd.DataFrame,
    metrics_full: pd.DataFrame,
    metrics_support: pd.DataFrame,
    deltas_full: pd.DataFrame,
    deltas_support: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablation: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics_support[metrics_support["method"].eq(winner)].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    support_counts = data.groupby(["split", "support_matched"]).size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["analytic_s03_timewalk", "traditional", "CFD20/50 S03-style time-walk fit with derivative residual correction; no event/run ids."],
            ["ridge", "linear ML", "Standardized ridge on waveform, CFD, pedestal, onset derivative, and curvature summaries; no stave one-hot or run id."],
            ["gradient_boosted_trees", "tree ML", "Histogram gradient-boosted trees on the same guardrailed features."],
            ["mlp", "neural tabular", "Two-layer MLP on the same guardrailed feature matrix."],
            ["1d_cnn_waveform_only", "neural waveform", "Compact 1D-CNN over only the normalized 18-sample waveform."],
            ["guardrail_orthogonal_edge_transformer_new", "new architecture", "Transformer over waveform, first derivative, and curvature channels with derivative-magnitude pooling; no amplitude, stave one-hot, duplicate readout, event id, or run id."],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S44a: S03 Guardrail-Orthogonal Cross-Sample CNN Timewalk Adoption Audit

## Abstract

Issue `#2414` asks whether the apparent Sample-II-trained CNN lift from ticket
`#2412` survives detector-identity guardrails.  I first reproduced the raw
B-stack selected-pulse count from ROOT, then trained on Sample-II analysis runs
`{config['train_runs']}` and evaluated transfer to Sample-I analysis plus run 64
`{config['heldout_runs']}`.  The benchmark compares analytic S03 time-walk,
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new guardrail-orthogonal edge
transformer.  The primary decision uses support-matched held-out pulses; the
winner named in `result.json` is **`{winner}`** with sigma68
`{best['sigma68_ns']:.4g} ns [{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are `data/root/root/hrdb_run_*.root`.  For each event, `HRDv` is
reshaped as `(8,18)`.  For B-stack stave channel `c`, baseline and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced registered count is

`N = sum_e sum_c 1[A_c > {config['amplitude_cut_adc']:.0f}]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group count is **{int(reproduction.iloc[-1]['selected_pulses'])}**, matching
the registered value exactly.  Hashes are written to `input_sha256.csv`; first rows:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimand

For fraction `f`, the CFD crossing is linearly interpolated before the pulse
maximum:

`t_f = k - 1 + (f A - y_(k-1)) / (y_k - y_(k-1))`,

where `y_t = x_t - b` and `k` is the first pre-peak sample with `y_k >= f A`.
The supervised target is the run/stave-centered onset residual

`Y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

This target implements the stave-offset residualization guardrail: stable
per-run and per-stave offsets are removed before any learner sees labels.

## Split, Support, and Uncertainty

The split unit is the run.  Sample-II analysis runs train the models; Sample-I
analysis runs and run 64 are never used for fitting.  Sampled rows:

{md_table(counts, ['split', 'rows'])}

Support matching removes held-out pulses outside the central training support in
amplitude and late-tail fraction, using quantiles `{config['support_quantiles']}`.

{md_table(support_counts, ['split', 'support_matched', 'rows'])}

Confidence intervals are 95% percentile intervals from
`{config['bootstrap_replicates']}` held-out run-block bootstrap resamples.  The
resolution metric is

`sigma_68(epsilon) = 0.5 * [Q_84(epsilon - median(epsilon)) - Q_16(epsilon - median(epsilon))]`.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is sensible here because the risk is detector identity
leakage from stave labels and amplitude-support tails.  The model is therefore
orthogonal to those channels by construction: it consumes only waveform shape,
first derivative, second derivative, and sample position, then gates the
transformer states by derivative magnitude before regression.

## Primary Support-Matched Results

{md_table(metrics_support, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

## Full-Transfer Results

{md_table(metrics_full, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

## Paired Deltas Against Analytic S03

Positive `delta_sigma68_ns` means worse resolution than the analytic comparator.

Support-matched domain:

{md_table(deltas_support, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high'])}

Full-transfer domain:

{md_table(deltas_full, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high'])}

## Run Stability

{md_table(by_run, ['domain', 'method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=160)}

## Guardrail and Systematic Strata

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=180)}

## Amplitude/Tail Exclusion Check

The table below refits tabular learners after removing explicit amplitude,
late-tail, late-window waveform, and late-derivative features.  It tests whether
tree/MLP gains are driven by the exact support tails flagged in ticket `#2412`.

{md_table(ablation, ['variant', 'domain', 'method', 'n', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'tail_fraction_abs_gt_5ns'], max_rows=60)}

## Interpretation and Caveats

The analysis supports adoption only if a learned model beats analytic S03 in the
support-matched domain and remains stable when amplitude/tail channels are
excluded.  It does not use run id, event id, duplicate readout, or stave one-hot
features.  The labels are waveform-derived CFD residuals, not external
picosecond truth.  The run-block bootstrap is intentionally conservative for
cross-sample transfer and can be wider than an event bootstrap.  The neural
models use a fixed small epoch budget; a larger architecture search could change
absolute rankings but would also increase leakage risk.

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
    s43 = load_s43()
    base = s43.load_base()
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

    data = s43.add_derivative_features(base.sample_pulses(config, rng))
    data = apply_ticket_split(data, config)
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)

    preds = {"analytic_s03_timewalk": s43.traditional_derivative_prediction(data, base)}
    preds.update(fit_tabular(data, amplitude_tail_excluded=False))
    preds["1d_cnn_waveform_only"] = base.fit_cnn(data, config, "1d_cnn_waveform_only", gated=False, seed=int(config["random_seed"]) + 1)
    preds["guardrail_orthogonal_edge_transformer_new"] = s43.fit_derivative_gate_transformer(
        data, config, seed=int(config["random_seed"]) + 2
    )

    pred_rows = []
    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        "support_matched",
        "evaluation_domain",
        "energy_bin",
        "pulse_shape_class",
        "pedestal_drift_bin",
        "late_tail_morphology",
    ]
    for method in METHOD_ORDER:
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["prediction_ns"] = preds[method]
        frame["error_ns"] = frame["target_onset_residual_ns"] - frame["prediction_ns"]
        pred_rows.append(frame)
    predictions = pd.concat(pred_rows, ignore_index=True)
    predictions.to_csv(out / "predictions.csv.gz", index=False)

    metrics_full, by_run_full, deltas_full = summarize(predictions, config, rng, "full_transfer")
    metrics_support, by_run_support, deltas_support = summarize(predictions, config, rng, "support_matched")
    by_run = pd.concat([by_run_full, by_run_support], ignore_index=True)
    strata = strata_summary(predictions)
    ablation = amplitude_tail_ablation(data, predictions, config, rng)

    metrics_full.to_csv(out / "metrics_full_transfer.csv", index=False)
    metrics_support.to_csv(out / "metrics_support_matched.csv", index=False)
    deltas_full.to_csv(out / "method_deltas_full_transfer.csv", index=False)
    deltas_support.to_csv(out / "method_deltas_support_matched.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    ablation.to_csv(out / "amplitude_tail_exclusion.csv", index=False)

    winner_row = metrics_support.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "issue_number": 2414,
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_ticket_text": config["claimed_ticket_text"],
        "claimed_once": True,
        "claim_command_invoked_once": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "manual_claim_recovery_note": "The required tn-ticket claim command returned a null pseudo-ticket because of issue #2413; #2414 was manually label-swapped to claimed for this worker without invoking claim again.",
        "raw_root_dir": str(base.raw_root_dir(config)),
        "git_commit": git_head(),
        "script_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(args.config),
        "runtime_sec": runtime,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "raw_number_reproduced_from_root": True
        },
        "split": {
            "train_runs": [int(r) for r in config["train_runs"]],
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "heldout_support_matched_rows": int(((data["split"] == "heldout") & data["support_matched"]).sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "split_unit": "run"
        },
        "guardrails": {
            "waveform_only_cnn": True,
            "stave_offset_residualized_target": True,
            "no_stave_one_hot": True,
            "no_run_or_event_id_features": True,
            "support_matched_primary_domain": True,
            "amplitude_tail_exclusion_table": "amplitude_tail_exclusion.csv"
        },
        "methods": METHOD_ORDER,
        "primary_metric": "support-matched held-out run-block bootstrap sigma68_ns of target_onset_residual_ns - prediction_ns; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ns_ci_low": float(winner_row["sigma68_ns_ci_low"]),
            "sigma68_ns_ci_high": float(winner_row["sigma68_ns_ci_high"]),
            "bias_ns": float(winner_row["bias_ns"]),
            "bias_ns_ci_low": float(winner_row["bias_ns_ci_low"]),
            "bias_ns_ci_high": float(winner_row["bias_ns_ci_high"])
        },
        "metric_table_support_matched": json_safe(metrics_support.to_dict("records")),
        "metric_table_full_transfer": json_safe(metrics_full.to_dict("records")),
        "paired_delta_table_support_matched": json_safe(deltas_support.to_dict("records")),
        "paired_delta_table_full_transfer": json_safe(deltas_full.to_dict("records")),
        "amplitude_tail_exclusion": json_safe(ablation.to_dict("records")),
        "novel_tickets_appended": [],
        "next_tickets": []
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(
        config,
        reproduction,
        input_hashes,
        data,
        metrics_full,
        metrics_support,
        deltas_full,
        deltas_support,
        by_run,
        strata,
        ablation,
        result,
        runtime,
    )
    (out / "manifest.json").write_text(json.dumps(artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")
    print(f"DONE {out} winner={result['winner']['method']} sigma68={result['winner']['sigma68_ns']:.4g} ns")


if __name__ == "__main__":
    main()
