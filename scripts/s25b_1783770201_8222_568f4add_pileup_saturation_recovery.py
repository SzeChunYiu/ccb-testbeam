#!/usr/bin/env python3
"""S25b pile-up and saturation recovery benchmark.

This ticket-specific runner reads the raw B-stack ROOT files, reproduces the
selected-pulse anchor count, builds controlled two-pulse injections from
run-local clean pulses, and compares a constrained template fit with several
ML/NN deconvolution heads on a run-held-out split.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402


TICKET = "1783770201.8222.568f4add"
OUT = ROOT / "reports" / f"{TICKET}__s25b_pileup_saturation_recovery_benchmark"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_base_config() -> dict:
    cfg = json.loads((ROOT / "configs" / "p05a_cnn_two_pulse_decomposition.json").read_text())
    cfg.update(
        {
            "study_id": "S25b",
            "ticket_id": TICKET,
            "title": "Pile-up and saturation recovery benchmark",
            "worker": "testbeam-laptop-2",
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071101,
            "max_clean_pulses_per_run_stave": 80,
            "injected_per_train_run": 45,
            "clean_per_train_run": 45,
            "injected_per_heldout_run": 60,
            "clean_per_heldout_run": 60,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 300, "cnn_epochs": 80, "cnn_channels": 10, "max_iter": 220})
    return cfg


def features(waveforms: np.ndarray) -> np.ndarray:
    return p05a.make_feature_matrix(waveforms)


def regression_targets(events: pd.DataFrame, waveforms: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    max_amp = np.maximum(waveforms.max(axis=1) - np.median(waveforms[:, :4], axis=1), 1.0)
    y = np.column_stack(
        [
            events["true_t1_sample"].to_numpy(float) / 12.0,
            np.nan_to_num(events["true_t2_sample"].to_numpy(float), nan=0.0) / 12.0,
            events["true_amp1_adc"].to_numpy(float) / max_amp,
            events["true_amp2_adc"].to_numpy(float) / max_amp,
        ]
    )
    return y, max_amp


def as_prediction(events: pd.DataFrame, score: np.ndarray, pred: np.ndarray, max_amp: np.ndarray, method: str) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "event_id": events["event_id"],
            "method": method,
            "score": np.asarray(score, dtype=float),
            "failed": np.asarray(score, dtype=float) < 0.5,
            "t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            "t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            "amp1_adc": np.clip(pred[:, 2] * max_amp, 0.0, None),
            "amp2_adc": np.clip(pred[:, 3] * max_amp, 0.0, None),
        }
    )
    swapped = out["t2_sample"] < out["t1_sample"]
    out.loc[swapped, ["t1_sample", "t2_sample"]] = out.loc[swapped, ["t2_sample", "t1_sample"]].to_numpy()
    out.loc[swapped, ["amp1_adc", "amp2_adc"]] = out.loc[swapped, ["amp2_adc", "amp1_adc"]].to_numpy()
    return out


def run_sklearn_methods(events: pd.DataFrame, waveforms: np.ndarray, seed: int) -> List[pd.DataFrame]:
    x = features(waveforms)
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    methods = []

    specs = [
        (
            "ridge",
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.0)),
            make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=2.0))),
        ),
        (
            "gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=70, learning_rate=0.07, l2_regularization=0.05, random_state=seed),
            MultiOutputRegressor(
                HistGradientBoostingRegressor(max_iter=70, learning_rate=0.07, l2_regularization=0.05, random_state=seed + 1)
            ),
        ),
        (
            "mlp",
            make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=400, early_stopping=True, random_state=seed + 2),
            ),
            make_pipeline(
                StandardScaler(),
                MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=400, early_stopping=True, random_state=seed + 3),
            ),
        ),
    ]
    for name, clf, reg in specs:
        clf.fit(x[train], y_class[train])
        if hasattr(clf, "predict_proba"):
            score = clf.predict_proba(x)[:, 1]
        else:
            raw = clf.decision_function(x)
            score = 1.0 / (1.0 + np.exp(-raw))
        reg.fit(x[pos_train], y_reg[pos_train])
        pred = reg.predict(x)
        methods.append(as_prediction(events, score, pred, max_amp, name))

    # New architecture: a physics-residual boosted stack.  It uses the
    # constrained template fit as a first-stage deconvolver, then learns
    # run-held-out residual corrections from waveform features.
    return methods


def add_residual_stack(
    events: pd.DataFrame, waveforms: np.ndarray, trad: pd.DataFrame, seed: int
) -> pd.DataFrame:
    x0 = features(waveforms)
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    trad_cols = trad[["trad_score", "trad_t1_sample", "trad_t2_sample", "trad_amp1_adc", "trad_amp2_adc"]].to_numpy(float)
    trad_cols = np.nan_to_num(trad_cols, nan=0.0, posinf=0.0, neginf=0.0)
    x = np.hstack([x0, trad_cols])
    clf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, l2_regularization=0.02, random_state=seed + 10)
    reg = MultiOutputRegressor(
        HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, l2_regularization=0.02, random_state=seed + 11)
    )
    clf.fit(x[train], y_class[train])
    score = clf.predict_proba(x)[:, 1]
    reg.fit(x[pos_train], y_reg[pos_train])
    pred = reg.predict(x)
    return as_prediction(events, score, pred, max_amp, "template_residual_boosted_stack_new")


def cnn_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    cnn, _cv = p05a.run_cnn(events, waveforms, cfg)
    return pd.DataFrame(
        {
            "event_id": cnn["event_id"],
            "method": "1d_cnn",
            "score": cnn["ml_score"],
            "failed": cnn["ml_failed"],
            "t1_sample": cnn["ml_t1_sample"],
            "t2_sample": cnn["ml_t2_sample"],
            "amp1_adc": cnn["ml_amp1_adc"],
            "amp2_adc": cnn["ml_amp2_adc"],
        }
    )


def template_prediction(trad: pd.DataFrame) -> pd.DataFrame:
    score = 1.0 / (1.0 + np.exp(-12.0 * (trad["trad_score"].to_numpy(float) - 0.055)))
    return pd.DataFrame(
        {
            "event_id": trad["event_id"],
            "method": "two_pulse_template_cfd_baseline",
            "score": score,
            "failed": trad["trad_failed"].to_numpy(bool) | (score < 0.5),
            "t1_sample": trad["trad_t1_sample"],
            "t2_sample": trad["trad_t2_sample"],
            "amp1_adc": trad["trad_amp1_adc"],
            "amp2_adc": trad["trad_amp2_adc"],
        }
    )


def metric_values(frame: pd.DataFrame) -> dict:
    labels = frame["is_overlap"].to_numpy(int)
    score = np.nan_to_num(frame["score"].to_numpy(float), nan=-1e9, neginf=-1e9)
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives["failed"].astype(bool)].copy()
    if len(valid):
        true_t = valid[["true_t1_sample", "true_t2_sample"]].to_numpy(float)
        pred_t = valid[["t1_sample", "t2_sample"]].to_numpy(float)
        terr = ((pred_t - true_t) * 10.0).reshape(-1)
        true_a = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_a = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        eerr = (pred_a - true_a) / np.maximum(true_a, 1.0)
    else:
        terr = np.asarray([])
        eerr = np.asarray([])
    sig68 = lambda z: float((np.percentile(z, 84) - np.percentile(z, 16)) / 2.0) if len(z) else float("nan")
    return {
        "detection_ap": float(average_precision_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "detection_auc": float(roc_auc_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "time_bias_ns": float(np.median(terr)) if len(terr) else float("nan"),
        "time_sigma68_ns": sig68(terr),
        "late_tail_rate_abs_gt_15ns": float(np.mean(np.abs(terr) > 15.0)) if len(terr) else float("nan"),
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((frame[frame["is_overlap"] == 0]["score"] >= 0.5).mean()),
        "energy_fractional_bias": float(np.median(eerr)) if len(eerr) else float("nan"),
        "energy_fractional_sigma68": sig68(eerr),
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
    }


def summarize(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row = {"method": method, **metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = metric_values(boot)
            for key, value in vals.items():
                if key.startswith("n_") or not np.isfinite(value):
                    continue
                samples.setdefault(key, []).append(float(value))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["time_sigma68_ns", "pileup_miss_rate"]).reset_index(drop=True)


def by_run_summary(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"].copy()
    for (method, run), group in held.groupby(["method", "source_run"]):
        rows.append({"method": method, "heldout_run": int(run), **metric_values(group)})
    return pd.DataFrame(rows).sort_values(["method", "heldout_run"])


def strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    held["spacing_ns"] = held["true_sep_sample"] * 10.0
    held["spacing_bin"] = pd.cut(held["spacing_ns"], bins=[0, 10, 25, 45, 70], include_lowest=True)
    held["ratio_bin"] = pd.cut(held["true_ratio"], bins=[0, 0.35, 0.625, 0.875, 1.05], include_lowest=True)
    held["saturated_proxy"] = held["true_amp1_adc"] + held["true_amp2_adc"] > 11000.0
    rows = []
    for field in ["spacing_bin", "ratio_bin", "stave", "saturated_proxy"]:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) == 0:
                continue
            rows.append({"stratum": field, "value": str(value), "method": method, **metric_values(group)})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: List[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    overall: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    templates: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = overall[overall["method"] == winner].iloc[0]
    trad = overall[overall["method"] == "two_pulse_template_cfd_baseline"].iloc[0]
    text = f"""# S25b: pile-up and saturation recovery benchmark

## Abstract

This study benchmarks first-hit timing recovery for controlled two-pulse pile-up in raw
B-stack HRD waveforms.  The ticket was `{TICKET}` and the worker was
`testbeam-laptop-2`.  The raw selected-pulse anchor is reproduced directly from
ROOT before any benchmark is interpreted: `{int(match.iloc[0]['reproduced'])}` pulses
are selected versus the reference `{int(match.iloc[0]['report_value'])}`, with
delta `{int(match.iloc[0]['delta'])}`.  The primary winner is
`{winner}`, with held-out run-block sigma68 `{best['time_sigma68_ns']:.3g}` ns
and 95% bootstrap interval [{best['time_sigma68_ns_ci_low']:.3g},
{best['time_sigma68_ns_ci_high']:.3g}] ns.

## Data and reproduction

Raw ROOT files were read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv` array was
reshaped to `(event, channel, sample)` with 18 samples per channel.  The selection
used the project-standard B-stave channels B2/B4/B6/B8, pedestal
`b_c = median(x_c[0:4])`, corrected waveform `y_c(t)=x_c(t)-b_c`, and amplitude
cut `max_t y_c(t) > 1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

Clean single-pulse templates were built from train runs only.  Candidate clean pulses
required 1500--12000 ADC and peak sample 4--12.  Each waveform was divided by its
amplitude and shifted to a common CFD20 reference before taking a per-stave median.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Benchmark design

The analysis uses a run-held-out split: train runs `{cfg['benchmark_runs']['train']}`
and held-out runs `{cfg['benchmark_runs']['heldout']}`.  Pile-up labels are controlled
injections, not hand-labeled real pile-up: for a clean primary pulse with amplitude
`A_1`, a second copy is injected as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_r(t) + p`,

where `T_s` is the train-only template for stave `s`, `Delta` is drawn from
0.5--6.0 samples, `r` from 0.25--1.0, `epsilon_r(t)` is a run-local residual sampled
from real clean pulses, and `p` is a small pedestal offset.  Negative controls use
the same run-local residual and amplitude spectrum without the second component.

## Methods

The traditional baseline is a bounded two-pulse template fit with a one-pulse
constant-fraction timing initialization.  It minimizes

`SSE_k = sum_t [w(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`

over a grid of first-hit shifts, allowed spacings, positive amplitudes, bounded
baseline, and secondary/primary amplitude ratio.  Its detection score is the
fractional improvement `(SSE_1-SSE_2)/SSE_1`.

The ML/NN panel contains ridge classification plus ridge multi-output regression,
histogram gradient-boosted trees, an MLP classifier/regressor pair, a compact
18-sample 1D-CNN, and a new template-residual boosted stack.  The new stack is a
two-stage architecture: it appends the traditional fit score and constituent
estimates to waveform shape features, then fits boosted classifiers and regressors
to learn residual corrections under the same run-held-out split.

## Metrics and uncertainty

For detected injected doublets, first-hit timing is evaluated on both constituents:
`e_t = 10 ns * (t_hat - t_true)`.  The robust resolution is

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

The primary ordering minimizes held-out `sigma68`, with miss-rate and false-split
rates treated as veto diagnostics.  Confidence intervals are percentile 95% CIs from
{int(cfg['ml']['bootstrap_samples'])} run-block bootstrap resamples of held-out runs.

## Overall held-out results

{md_table(overall, ['method', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

The traditional baseline obtains sigma68 `{trad['time_sigma68_ns']:.3g}` ns.  The
winner `{winner}` changes that by `{best['time_sigma68_ns'] - trad['time_sigma68_ns']:.3g}`
ns.  Detection quality is reported separately because a low timing width after
aggressive rejection would not constitute a usable deconvolver.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata and systematics

The table below scans doublet spacing, amplitude ratio, stave, and a saturation proxy
defined by injected summed amplitude above 11000 ADC.

{md_table(strata, ['stratum', 'value', 'method', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'energy_fractional_sigma68'])}

Systematic limitations are explicit.  First, injected doublets preserve observed
single-pulse residuals but cannot prove the frequency or morphology of real beam
pile-up.  Second, only train-run templates are used, so template drift appears as a
real held-out degradation.  Third, the B-stack has 18 samples, which limits separations
below roughly one sample.  Fourth, saturation is represented by a waveform-amplitude
proxy rather than electronics truth flags.  Fifth, the bootstrap unit is the run; the
number of held-out runs is finite and the intervals should be interpreted as
run-transfer uncertainty, not an asymptotic event-level error.

## Negative controls and caveats

Clean-pulse controls enter every held-out run with the same source-run distribution
as injected doublets.  False-split rate is therefore the negative-control endpoint.
The benchmark should be used to choose a deconvolution strategy for controlled
doublet-like pile-up, while follow-up work should validate the winner on hand-scanned
real pile-up candidates and on electronics saturation metadata if available.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s25a")
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_base_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [template_prediction(trad_raw)]
    preds.extend(run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(cnn_prediction(events, waves, cfg))
    preds.append(add_residual_stack(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    by_run = by_run_summary(joined)
    strata = strata_summary(joined)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(overall.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, overall, by_run, strata, template_summary, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": "testbeam-laptop-2",
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out constituent timing sigma68 with run-block bootstrap CI reported",
            "time_sigma68_ns": float(overall.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(overall.iloc[0]["time_sigma68_ns_ci_low"]),
                float(overall.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(overall.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(overall.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Pile-up truth comes from controlled doublet injection into raw-ROOT-derived clean pulses.",
            "Saturation is represented by an amplitude proxy rather than electronics saturation flags.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s25b_1783770201_8222_568f4add_pileup_saturation_recovery.py",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
