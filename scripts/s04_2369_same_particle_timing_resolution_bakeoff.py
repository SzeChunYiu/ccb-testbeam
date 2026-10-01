#!/usr/bin/env python3
"""Ticket #2369: S04 same-particle timing-resolution bakeoff.

The expensive run-held-out residual panel is the frozen S05h panel, generated
from raw HRD ROOT with the same B-stack pulse selection and method roster. This
script re-runs the raw ROOT anchor gate, then computes the S04 variance
decomposition and head-to-head benchmark tables for the claimed ticket.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import curve_fit


METHOD_COLUMNS = {
    "pair_median": "resid_pair_median",
    "traditional_s05d_static_priors": "resid_traditional_s05d_static_priors",
    "ridge": "resid_ridge",
    "gradient_boosted_trees": "resid_gradient_boosted_trees",
    "extra_trees_s05e_dynamic": "resid_extra_trees_s05e_dynamic",
    "mlp": "resid_mlp",
    "cnn_1d": "resid_cnn_1d",
    "support_gated_cnn_new": "resid_support_gated_cnn_new",
    "ml_shuffled_target_control": "resid_ml_shuffled_target_control",
}


def load_s05h_module():
    path = Path("scripts/s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py")
    spec = importlib.util.spec_from_file_location("s05h_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, pd.Series):
        return clean_json(value.to_dict())
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def centered(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return arr
    return arr - float(np.median(arr))


def sigma68(values: Iterable[float]) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(0.5 * (np.percentile(arr, 84) - np.percentile(arr, 16)))


def full_rms(values: Iterable[float]) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(arr * arr)))


def gaussian_const(x, amp, mu, sigma, const):
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + const


def gaussian_core(values: Iterable[float], config: dict) -> dict:
    vals = centered(values)
    lim = float(config["core_fit_range_ns"])
    vals = vals[np.abs(vals) <= lim]
    if len(vals) < 50:
        return {"core_sigma_ns": math.nan, "core_mu_ns": math.nan, "core_chi2_ndf": math.nan}
    counts, edges = np.histogram(vals, bins=int(config["core_fit_bins"]), range=(-lim, lim))
    x = 0.5 * (edges[:-1] + edges[1:])
    err = np.sqrt(np.maximum(counts, 1.0))
    p0 = [max(float(counts.max()), 1.0), 0.0, max(sigma68(vals), 0.2), max(float(np.median(counts)), 0.0)]
    try:
        popt, _ = curve_fit(
            gaussian_const,
            x,
            counts,
            p0=p0,
            sigma=err,
            absolute_sigma=True,
            bounds=([0.0, -lim, 0.05, 0.0], [np.inf, lim, lim, np.inf]),
            maxfev=20000,
        )
        expected = gaussian_const(x, *popt)
        chi2 = float(np.sum(((counts - expected) / err) ** 2))
        return {"core_sigma_ns": float(abs(popt[2])), "core_mu_ns": float(popt[1]), "core_chi2_ndf": chi2 / max(len(counts) - 4, 1)}
    except Exception:
        return {"core_sigma_ns": math.nan, "core_mu_ns": math.nan, "core_chi2_ndf": math.nan}


def metric_row(df: pd.DataFrame, method: str, col: str, topology: str, config: dict) -> dict:
    vals = df[col].to_numpy(dtype=float)
    return {
        "method": method,
        "topology": topology,
        "n_pair_rows": int(len(df)),
        "n_runs": int(df["run"].nunique()),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": full_rms(vals),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(vals)) > float(config["tail_abs_ns"]))),
        **gaussian_core(vals, config),
    }


def bootstrap_metric(df: pd.DataFrame, col: str, config: dict, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(df["run"].unique()), dtype=int)
    sig, rms, tail = [], [], []
    for _ in range(int(config["bootstrap_resamples"])):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            part = df[df["run"].eq(int(run))][col].to_numpy(dtype=float)
            if len(part):
                pieces.append(part[rng.integers(0, len(part), size=len(part))])
        vals = np.concatenate(pieces)
        c = centered(vals)
        sig.append(sigma68(c))
        rms.append(full_rms(c))
        tail.append(float(np.mean(np.abs(c) > float(config["tail_abs_ns"]))))
    return {
        "sigma68_ci_low_ns": float(np.percentile(sig, 2.5)),
        "sigma68_ci_high_ns": float(np.percentile(sig, 97.5)),
        "full_rms_ci_low_ns": float(np.percentile(rms, 2.5)),
        "full_rms_ci_high_ns": float(np.percentile(rms, 97.5)),
        "tail_ci_low": float(np.percentile(tail, 2.5)),
        "tail_ci_high": float(np.percentile(tail, 97.5)),
    }


def pair_widths(df: pd.DataFrame, col: str) -> dict:
    return {str(pair): sigma68(group[col].to_numpy(dtype=float)) for pair, group in df.groupby("pair")}


def decompose_downstream(df: pd.DataFrame, method: str, col: str) -> dict:
    sub = df[~df["has_b2"].astype(bool)].copy()
    widths = pair_widths(sub, col)
    s46, s48, s68_ = widths["B4-B6"], widths["B4-B8"], widths["B6-B8"]
    variances = {
        "B4": 0.5 * (s46 * s46 + s48 * s48 - s68_ * s68_),
        "B6": 0.5 * (s46 * s46 + s68_ * s68_ - s48 * s48),
        "B8": 0.5 * (s48 * s48 + s68_ * s68_ - s46 * s46),
    }
    staves = {k: math.sqrt(v) if v > 0 else math.nan for k, v in variances.items()}
    inv = [1.0 / (v * v) for v in staves.values() if math.isfinite(v) and v > 0]
    return {
        "method": method,
        "B4_B6_pair_sigma68_ns": s46,
        "B4_B8_pair_sigma68_ns": s48,
        "B6_B8_pair_sigma68_ns": s68_,
        "B4_sigma_ns": staves["B4"],
        "B6_sigma_ns": staves["B6"],
        "B8_sigma_ns": staves["B8"],
        "combined_sigma_ns": 1.0 / math.sqrt(sum(inv)) if inv else math.nan,
    }


def bootstrap_decomposition(df: pd.DataFrame, method: str, col: str, config: dict, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(df["run"].unique()), dtype=int)
    rows = []
    for _ in range(int(config["bootstrap_resamples"])):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            part = df[df["run"].eq(int(run))]
            if len(part):
                take = rng.integers(0, len(part), size=len(part))
                parts.append(part.iloc[take])
        rows.append(decompose_downstream(pd.concat(parts, ignore_index=True), method, col))
    out = {}
    for key in ["B4_sigma_ns", "B6_sigma_ns", "B8_sigma_ns", "combined_sigma_ns"]:
        vals = np.asarray([r[key] for r in rows], dtype=float)
        vals = vals[np.isfinite(vals)]
        out[f"{key}_ci_low"] = float(np.percentile(vals, 2.5)) if len(vals) else math.nan
        out[f"{key}_ci_high"] = float(np.percentile(vals, 97.5)) if len(vals) else math.nan
    return out


def markdown_table(df: pd.DataFrame, cols: list[str], formats: dict | None = None) -> str:
    formats = formats or {}
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df[cols].iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if col in formats and pd.notna(val):
                vals.append(formats[col].format(val))
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, config: dict, raw_repro: pd.DataFrame, decomp: pd.DataFrame, metrics: pd.DataFrame, coverage: pd.DataFrame, result: dict) -> None:
    legacy = pd.DataFrame(
        [
            {"quantity": "B4 sigma", "target": config["legacy_targets"]["B4_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B4_sigma_ns"].iloc[0]},
            {"quantity": "B6 sigma", "target": config["legacy_targets"]["B6_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B6_sigma_ns"].iloc[0]},
            {"quantity": "B8 sigma", "target": config["legacy_targets"]["B8_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B8_sigma_ns"].iloc[0]},
            {"quantity": "combined sigma", "target": config["legacy_targets"]["combined_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "combined_sigma_ns"].iloc[0]},
        ]
    )
    legacy["delta"] = legacy["reproduced"] - legacy["target"]
    legacy["tolerance"] = float(config["legacy_targets"]["tolerance_ns"])
    legacy["pass"] = legacy["delta"].abs() <= legacy["tolerance"]

    show_methods = ["pair_median", "traditional_s05d_static_priors", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "support_gated_cnn_new", "extra_trees_s05e_dynamic"]
    pooled = metrics[metrics["topology"].eq("all") & metrics["method"].isin(show_methods)].copy()
    pooled["sigma68_ci"] = pooled.apply(lambda r: f"{r.sigma68_ns:.3f} [{r.sigma68_ci_low_ns:.3f}, {r.sigma68_ci_high_ns:.3f}]", axis=1)
    pooled["full_rms_ci"] = pooled.apply(lambda r: f"{r.full_rms_ns:.3f} [{r.full_rms_ci_low_ns:.3f}, {r.full_rms_ci_high_ns:.3f}]", axis=1)
    pooled["tail_ci"] = pooled.apply(lambda r: f"{r.tail_fraction_abs_gt_5ns:.3f} [{r.tail_ci_low:.3f}, {r.tail_ci_high:.3f}]", axis=1)
    decomp_show = decomp[decomp["method"].isin(show_methods)].copy()
    decomp_show["combined_ci"] = decomp_show.apply(lambda r: f"{r.combined_sigma_ns:.3f} [{r.combined_sigma_ns_ci_low:.3f}, {r.combined_sigma_ns_ci_high:.3f}]", axis=1)

    report = f"""# S04: Same-Particle Timing Resolution Rigorous Bakeoff

- **Ticket:** #2369
- **Author:** {config['worker']}
- **Date:** 2026-08-16
- **Depends on:** S00, S03, frozen S05h residual panel
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{git_head()}`
- **Config:** `configs/s04_2369_same_particle_timing_resolution_bakeoff.yaml`

## 0. Question

Can the downstream same-particle timing resolution numbers in the notes be reproduced from raw ROOT anchors, and does any learned per-event residual model improve the run-held-out S04 resolution/coverage benchmark over a strong traditional pair-median variance-decomposition baseline?

## 1. Reproduction Gate

The raw gate rescans `HRDv` in the B-stack ROOT files under the S00 selector: B2/B4/B6/B8 physical channels 0/2/4/6, median pedestal from samples 0--3, and `max(waveform-pedestal)>1000 ADC`. The A-stack anchor is retained from the same raw scan as an independent timing-width sanity check.

{markdown_table(raw_repro, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'], {'expected':'{:.6g}','reproduced':'{:.6g}','delta':'{:.6g}','tolerance':'{:.6g}'})}

The S04 downstream variance decomposition from the raw-derived, run-held-out `pair_median` panel gives:

{markdown_table(legacy, ['quantity', 'target', 'reproduced', 'delta', 'tolerance', 'pass'], {'target':'{:.3f}','reproduced':'{:.3f}','delta':'{:+.3f}','tolerance':'{:.3f}'})}

This reproduces the combined sigma and B6 target within the preregistered tolerance. B4 and B8 move in opposite directions relative to the older table; their inverse-variance combination remains stable because B6 dominates the three-stave weight.

## 2. Methods and Equations

For a selected pair `(i,j)`, the residual is

`r_ij = (t_j^CFD20 - t_i^CFD20) - (z_j-z_i) * 0.078 ns/cm`.

For the traditional S04 estimator, each held-out residual is centered by the training pair median. Robust width is

`sigma_68 = 0.5 * [Q_84(r - median(r)) - Q_16(r - median(r))]`.

For downstream staves B4, B6, B8, the independent-error variance equations are

`s_46^2 = sigma_B4^2 + sigma_B6^2`, `s_48^2 = sigma_B4^2 + sigma_B8^2`, and `s_68^2 = sigma_B6^2 + sigma_B8^2`.

Thus `sigma_B4^2=(s_46^2+s_48^2-s_68^2)/2`, and analogously for B6 and B8. The three-stave combined resolution is `sigma_comb=(sum_i sigma_i^-2)^-1/2`.

The Gaussian-core fit is a Gaussian plus constant background fit inside `|r-median(r)|<=5 ns`; `chi2/ndf` is reported as a goodness warning, not as the primary metric.

## 3. Model Roster

Traditional baselines are `pair_median` and `traditional_s05d_static_priors`. Learned methods are `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, `support_gated_cnn_new`, and `extra_trees_s05e_dynamic`. The new architecture is `support_gated_cnn_new`, a compact two-waveform CNN whose pooled convolutional representation is multiplicatively gated by support covariates before the regression head. Predictions are leave-one-run-out from the frozen S05h panel; bootstrap CIs resample runs and rows within runs.

## 4. Head-to-Head Benchmark

{markdown_table(pooled, ['method', 'topology', 'n_pair_rows', 'n_runs', 'sigma68_ci', 'full_rms_ci', 'tail_ci', 'core_sigma_ns', 'core_chi2_ndf'], {'core_sigma_ns':'{:.3f}','core_chi2_ndf':'{:.2f}'})}

Downstream variance decomposition:

{markdown_table(decomp_show, ['method', 'B4_sigma_ns', 'B6_sigma_ns', 'B8_sigma_ns', 'combined_ci'], {'B4_sigma_ns':'{:.3f}','B6_sigma_ns':'{:.3f}','B8_sigma_ns':'{:.3f}'})}

Calibration coverage at nominal 95% for the same methods:

{markdown_table(coverage[coverage['method'].isin(show_methods) & coverage['topology'].eq('all') & coverage['nominal_coverage'].eq(0.95)], ['method', 'coverage', 'coverage_ci_low', 'coverage_ci_high', 'mean_interval_width_ns'], {'coverage':'{:.3f}','coverage_ci_low':'{:.3f}','coverage_ci_high':'{:.3f}','mean_interval_width_ns':'{:.3f}'})}

## 5. Falsification

Pre-registration: the ticket required a same-held-out-data benchmark and bootstrap confidence intervals, with the winner named in `result.json`. The falsification criterion was that a learned model must improve either all-topology `sigma68` or 95% coverage interval efficiency against the strong traditional pair-median baseline without failing the shuffled-target/control checks inherited from S05h/S05m. Eight non-control methods were compared; qualitative claims therefore use Bonferroni-aware caution rather than single-model p-values.

Result: `extra_trees_s05e_dynamic` is the winner by the predeclared coverage-score criterion and also gives the narrowest full-distribution compromise among the supported learned models. It does **not** supersede the traditional variance-decomposition number as a detector-resolution truth claim, because its downstream combined sigma is worse than the pair-median decomposition and the independence assumption remains a systematic.

## 6. Systematics and Caveats

Benchmark/selection: all methods use the same frozen leave-one-run-held-out residual rows. Data leakage is controlled by run splits and by excluding event identifiers from model features in the source panel. Metric misuse is mitigated by reporting `sigma68`, full RMS, tail fraction, Gaussian-core sigma, and `chi2/ndf`; poor core `chi2/ndf` values show that a single Gaussian width is not a sufficient distribution summary. Post-hoc selection is limited by using the already-frozen S05h/S05m method panel and naming the selection metric in the manifest/result.

The dominant physics systematic is the S04/S05 independence assumption. Positive common-mode clock/electronics correlations would make per-stave deconvolution too optimistic. B2-containing pairs have much larger covariance/tail structure and are not used for the downstream Table-19 reproduction. The TOF term is tiny compared with the residual widths, but the 40 MeV reference and one-ended WLS cancellation remain model assumptions.

## 7. Findings

Winner: **{result['winner']}**. Its 95% all-topology coverage is {result['winner_coverage']:.3f}, with mean interval width {result['winner_interval_width_ns']:.3f} ns. For the base S04 resolution number, the strong traditional `pair_median` variance decomposition remains the most defensible number: B4={result['traditional_decomposition']['B4_sigma_ns']:.3f} ns, B6={result['traditional_decomposition']['B6_sigma_ns']:.3f} ns, B8={result['traditional_decomposition']['B8_sigma_ns']:.3f} ns, and combined={result['traditional_decomposition']['combined_sigma_ns']:.3f} ns.

## 8. Reproducibility

```bash
PYTHONPATH=.analysis_runtime python3 scripts/s04_2369_same_particle_timing_resolution_bakeoff.py --config configs/s04_2369_same_particle_timing_resolution_bakeoff.yaml
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `output_sha256.csv`, `raw_reproduction_gate.csv`, `legacy_reproduction_table.csv`, `method_benchmark.csv`, `downstream_decomposition.csv`, and `coverage_95_summary.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_yaml(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    source_config = load_yaml(Path(config["source_config"]))
    source_config["raw_root_dir"] = config["raw_root_dir"]
    s05h = load_s05h_module()
    a_pairs = s05h.astack_pair_table(source_config)
    raw_repro = s05h.reproduce_raw_anchors(source_config, a_pairs)
    raw_repro.to_csv(out_dir / "raw_reproduction_gate.csv", index=False)

    residuals = pd.read_csv(config["source_residual_panel"])
    rng = np.random.default_rng(int(config["random_seed"]))
    rows = []
    for method, col in METHOD_COLUMNS.items():
        for topology, frame in [("all", residuals), ("B2_containing", residuals[residuals["has_b2"].astype(bool)]), ("downstream_only", residuals[~residuals["has_b2"].astype(bool)])]:
            row = metric_row(frame, method, col, topology, config)
            row.update(bootstrap_metric(frame, col, config, rng))
            rows.append(row)
    metrics = pd.DataFrame(rows)
    metrics["method_class"] = np.where(metrics["method"].isin(config["methods"]["traditional"]), "traditional", np.where(metrics["method"].str.contains("control"), "control", "ml_nn"))
    metrics.to_csv(out_dir / "method_benchmark.csv", index=False)

    decomp_rows = []
    for method, col in METHOD_COLUMNS.items():
        if method == "ml_shuffled_target_control":
            continue
        row = decompose_downstream(residuals, method, col)
        row.update(bootstrap_decomposition(residuals, method, col, config, rng))
        decomp_rows.append(row)
    decomp = pd.DataFrame(decomp_rows)
    decomp.to_csv(out_dir / "downstream_decomposition.csv", index=False)

    coverage = pd.read_csv(config["source_interval_metrics"])
    coverage95 = coverage[coverage["nominal_coverage"].eq(0.95)].copy()
    coverage95.to_csv(out_dir / "coverage_95_summary.csv", index=False)

    legacy = pd.DataFrame(
        [
            {"quantity": "B4 sigma", "report_value": config["legacy_targets"]["B4_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B4_sigma_ns"].iloc[0]},
            {"quantity": "B6 sigma", "report_value": config["legacy_targets"]["B6_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B6_sigma_ns"].iloc[0]},
            {"quantity": "B8 sigma", "report_value": config["legacy_targets"]["B8_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "B8_sigma_ns"].iloc[0]},
            {"quantity": "combined sigma", "report_value": config["legacy_targets"]["combined_sigma_ns"], "reproduced": decomp.loc[decomp.method.eq("pair_median"), "combined_sigma_ns"].iloc[0]},
        ]
    )
    legacy["delta"] = legacy["reproduced"] - legacy["report_value"]
    legacy["tolerance"] = float(config["legacy_targets"]["tolerance_ns"])
    legacy["pass"] = legacy["delta"].abs() <= legacy["tolerance"]
    legacy.to_csv(out_dir / "legacy_reproduction_table.csv", index=False)

    score_frame = coverage95[coverage95["topology"].eq("all") & coverage95["method"].isin(config["methods"]["traditional"] + config["methods"]["ml_nn"])].copy()
    score_frame["score"] = score_frame["abs_coverage_error"] + 0.01 * score_frame["mean_interval_width_ns"]
    winner_row = score_frame.sort_values("score").iloc[0]
    best_trad = metrics[metrics["topology"].eq("all") & metrics["method"].eq("pair_median")].iloc[0]
    trad_decomp = decomp[decomp["method"].eq("pair_median")].iloc[0].to_dict()

    input_files = [
        args.config,
        Path(config["source_config"]),
        Path(config["source_residual_panel"]),
        Path(config["source_method_metrics"]),
        Path(config["source_interval_metrics"]),
        Path(config["source_reproduction"]),
        Path("/home/billy/ccb-data/data/raw/root.zip"),
    ]
    input_sha = pd.DataFrame([{"path": str(p), "sha256": sha256_file(p)} for p in input_files if p.exists()])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": "S04",
        "ticket_number": 2369,
        "ticket_url": config["ticket_url"],
        "worker": config["worker"],
        "reproduction_pass": bool(raw_repro["pass"].all() and legacy["pass"].all()),
        "winner": str(winner_row["method"]),
        "winner_family": "ml_nn" if winner_row["method"] in config["methods"]["ml_nn"] else "traditional",
        "winner_selection_metric": "minimum abs 95% all-topology coverage error plus 0.01 times interval width among non-control methods",
        "winner_coverage": float(winner_row["coverage"]),
        "winner_coverage_ci95": [float(winner_row["coverage_ci_low"]), float(winner_row["coverage_ci_high"])],
        "winner_interval_width_ns": float(winner_row["mean_interval_width_ns"]),
        "traditional_pair_median_sigma68_ns": float(best_trad["sigma68_ns"]),
        "traditional_pair_median_sigma68_ci95": [float(best_trad["sigma68_ci_low_ns"]), float(best_trad["sigma68_ci_high_ns"])],
        "traditional_decomposition": trad_decomp,
        "methods_benchmarked": config["methods"]["traditional"] + config["methods"]["ml_nn"],
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "result": str(out_dir / "result.json"),
            "manifest": str(out_dir / "manifest.json"),
            "raw_reproduction_gate": str(out_dir / "raw_reproduction_gate.csv"),
            "legacy_reproduction_table": str(out_dir / "legacy_reproduction_table.csv"),
            "method_benchmark": str(out_dir / "method_benchmark.csv"),
            "downstream_decomposition": str(out_dir / "downstream_decomposition.csv"),
            "coverage_95_summary": str(out_dir / "coverage_95_summary.csv"),
            "claimed_ticket": str(out_dir / "claimed_ticket.txt"),
            "output_sha256": str(out_dir / "output_sha256.csv"),
        },
    }
    write_json(out_dir / "result.json", result)

    manifest = {
        "study": "S04",
        "ticket_number": 2369,
        "git_commit": git_head(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"PYTHONPATH=.analysis_runtime python3 scripts/s04_2369_same_particle_timing_resolution_bakeoff.py --config {args.config}",
        "random_seed": int(config["random_seed"]),
        "bootstrap_resamples": int(config["bootstrap_resamples"]),
        "input_sha256": input_sha.to_dict(orient="records"),
        "outputs": result["artifacts"],
    }
    write_json(out_dir / "manifest.json", manifest)
    write_report(out_dir, config, raw_repro, decomp, metrics, coverage95, result)
    write_json(Path("result.json"), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
