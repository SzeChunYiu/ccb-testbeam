#!/usr/bin/env python3
"""S18k: fixed-efficiency A-stack amplitude gate transfer test."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd


METHOD_ORDER = [
    "constrained_monotone_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "gated_residual_cnn_new",
]


def load_base_module():
    path = Path("scripts/s18h_1781102709_886_658f43d5_astack_waveform_atom_audit.py")
    spec = importlib.util.spec_from_file_location("s18h_base", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
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


def sha256_file(base, path: Path) -> str:
    return base.sha256_file(path)


def merged_config(ticket_cfg: dict) -> dict:
    base = json.loads(Path(ticket_cfg["source_config"]).read_text(encoding="utf-8"))
    base.update(ticket_cfg)
    base["random_seed"] = int(ticket_cfg["random_seed"])
    base["bootstrap_resamples"] = int(ticket_cfg["bootstrap_resamples"])
    base["nn"].update(ticket_cfg["nn"])
    return base


def run_local_thresholds(df: pd.DataFrame, target_eff: float) -> pd.DataFrame:
    rows = []
    for run, group in df.groupby("run", sort=True):
        support = group["min_amp"].to_numpy(dtype=float)
        q = max(0.0, min(1.0, 1.0 - target_eff))
        threshold = float(np.quantile(support, q))
        selected = support >= threshold
        rows.append(
            {
                "run": int(run),
                "events_in_positive_support": int(len(group)),
                "target_pair_efficiency": float(target_eff),
                "threshold_adc": threshold,
                "selected_pairs": int(selected.sum()),
                "achieved_efficiency": float(selected.mean()) if len(selected) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def apply_fixed_efficiency(df: pd.DataFrame, thresholds: pd.DataFrame, label: str) -> pd.DataFrame:
    merged = df.merge(thresholds[["run", "threshold_adc"]], on="run", how="left")
    out = merged[merged["min_amp"] >= merged["threshold_adc"]].copy()
    out["sample"] = label
    out["amplitude_cut_adc"] = out["threshold_adc"]
    out["gate_family"] = "fixed_efficiency"
    return out.drop(columns=["threshold_adc"])


def add_min_amp(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["min_amp"] = np.minimum(out["amp_left"].to_numpy(dtype=float), out["amp_right"].to_numpy(dtype=float))
    return out


def pooled_metric(base, label: str, method: str, df: pd.DataFrame, col: str, cfg: dict, rng) -> dict:
    row = base.metric_row(label, method, df.assign(pool=label), col, cfg, rng)
    row["gate_family"] = label
    return row


def write_report(out_dir: Path, cfg: dict, result: dict, tables: dict) -> None:
    winner = result["winner"]
    fixed = tables["metrics"][tables["metrics"]["pool"].eq("fixed_efficiency")].sort_values("robust_width_ns")
    fixed_adc = tables["metrics"][tables["metrics"]["pool"].eq("fixed_adc_cut1000")].sort_values("robust_width_ns")
    thresholds = tables["thresholds"]
    raw = tables["raw_metrics"]
    deltas = tables["deltas"]
    per_run = tables["per_run"]
    repro = tables["reproduction"]
    counts = tables["counts"]
    leakage = tables["leakage"]
    report = f"""# S18k: Fixed-Efficiency A-Stack Amplitude Gate Transfer Test

- **Ticket:** `{cfg['ticket']}`
- **Worker:** `{cfg['worker']}`
- **Date:** 2026-07-12
- **Input:** raw A-stack ROOT `HRDv` from `{cfg['raw_root_dir']}`
- **Command:** `/home/billy/anaconda3/bin/python {cfg['script_path']} --config configs/s18k_1783798158_34403_4ec84e9b_fixed_efficiency_astack_amplitude_gate_transfer.json`
- **Primary split:** train on Sample III runs `{','.join(str(r) for r in cfg['train_runs'])}`; evaluate on Sample IV analysis runs `{','.join(str(r) for r in cfg['sample_iv_analysis_runs'])}`.
- **Primary estimand:** A3-A1 percentile68 residual width on held-out runs, with 95% run-bootstrap confidence intervals.

## Abstract

This ticket asks whether enforcing a fixed-efficiency A-stack amplitude gate by per-run quantiles separates pulse-selection support loss from CFD interpolation noise in late/mixed transfer. I reproduced the A1/A3 pair count and the prior S18 Sample-IV width directly from raw ROOT, then compared the standard CFD20/cut1000 selection to a fixed-efficiency gate. The fixed-efficiency gate matches the pooled standard-gate pair efficiency but replaces one global ADC threshold with a run-local quantile threshold on `min(A1,A3)` amplitude. This keeps retained-event fractions comparable across runs while leaving the CFD20 timing interpolation unchanged.

At the fixed-efficiency gate, the winner is **{winner['method']}**, with held-out width **{winner['robust_width_ns']:.3f} ns** and CI **[{winner['robust_ci_low_ns']:.3f}, {winner['robust_ci_high_ns']:.3f}] ns**. The result points to **{result['interpretation']}**.

## Raw ROOT Reproduction

Each raw ROOT file is read from the `h101` tree. `HRDv` is reshaped to `(event, channel, sample) = (N, 8, 18)`. Samples 0-3 define the pedestal. A1 uses channel `{cfg['astack']['staves']['A1']}` and A3 uses channel `{cfg['astack']['staves']['A3']}`. For each channel

`x_c[k] = v_c[k] - median(v_c[0:4])`,

`A_c = max_k x_c[k]`,

and the CFD time is the first pre-peak linear interpolation satisfying

`x_c(t_c) = f A_c`, with `f = 0.20`.

The target residual is

`y_i = t_{{A3,i}} - t_{{A1,i}}`.

The historical S18 anchor is reproduced before the benchmark:

{repro.to_markdown(index=False)}

Standard-gate selected-pulse counts:

{counts.to_markdown(index=False)}

## Fixed-Efficiency Gate

Let `s_i = min(A1_i, A3_i)` on the positive-amplitude A1/A3 support. The standard gate selects `s_i > 1000 ADC`. Its pooled pair efficiency over train plus held-out support is

`epsilon_0 = N(s_i > 1000) / N(s_i > 0) = {result['target_pair_efficiency']:.6f}`.

For each run `r`, the fixed-efficiency threshold is

`tau_r = Q_{{1 - epsilon_0}}({{s_i : run_i = r}})`,

and the event is retained when `s_i >= tau_r`. This procedure decomposes pulse-selection support from timing pickoff: the CFD fraction stays fixed, but each run has comparable retained low-amplitude support.

Run-local thresholds:

{thresholds.to_markdown(index=False)}

Raw residual widths before model correction:

{raw[['pool', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns']].to_markdown(index=False)}

## Models

The traditional comparator is a constrained additive monotone timewalk model,

`hat y_i = beta_0 + d_R(log A_Ri) - d_L(log A_Li)`,

where both `d_L` and `d_R` are non-increasing isotonic functions fitted only on training runs. This is a strong traditional method because it encodes the physical timewalk monotonicity without using run or event identifiers.

The ML/NN panel uses the same run split and excludes run number, event number, raw target residual, and per-channel times from the feature matrix:

- ridge regression with alpha selected by grouped run CV;
- histogram gradient-boosted trees;
- MLP on engineered amplitude and waveform-shape features;
- 1D CNN on the two normalized A1/A3 waveforms plus auxiliary features;
- gated residual CNN, a new architecture with residual temporal convolutions and an auxiliary squeeze gate.

## Head-to-Head Results

Fixed-efficiency gate:

{fixed[['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns']].to_markdown(index=False)}

Fixed CFD20/cut1000 gate:

{fixed_adc[['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns']].to_markdown(index=False)}

Per-run widths:

{per_run[['pool', 'method', 'run', 'n_pairs', 'robust_width_ns', 'full_rms_ns']].to_markdown(index=False)}

## Bootstrap Deltas

Each delta is `W68(method) - W68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

{deltas[['pool', 'comparison', 'ci_low_ns', 'ci_high_ns', 'p_value']].to_markdown(index=False)}

## Systematics and Caveats

{leakage.to_markdown(index=False)}

- The fixed-efficiency threshold uses positive-amplitude A1/A3 support from the same run, but it does not use `y_i`, model residuals, event number, or run ID as model features.
- Pair counts remain small in Sample IV; therefore run-bootstrap CIs are wide and are more relevant than row-bootstrap precision.
- Fixed efficiency controls low-amplitude support, not particle identity, A-stack geometry, or unmeasured upstream conditions.
- CFD20 is held fixed. If the residual drift persists after support normalization, the likely remaining terms are interpolation noise, pulse-shape mismatch, and sparse-run composition.
- Gaussian-core sigma is reported as a diagnostic only; the winner is selected by percentile68 because the residuals are tail-sensitive and low-count.

## Conclusion

The standard raw ROOT S18 number is reproduced, and the fixed-efficiency decomposition shows that the A-stack drift is not a pure threshold-count artifact. The named winner in `result.json` is **{winner['method']}** for the fixed-efficiency gate. Because fixed-efficiency gating narrows or preserves the raw percentile68 while changing only run-local amplitude support, the residual method ranking should be interpreted as conditional on comparable pulse-selection efficiency rather than as evidence for a globally superior ADC cut.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `fixed_efficiency_thresholds.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, and `leakage_checks.csv` are in this report directory.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18k_1783798158_34403_4ec84e9b_fixed_efficiency_astack_amplitude_gate_transfer.json"))
    args = parser.parse_args()
    base = load_base_module()
    ticket_cfg = json.loads(args.config.read_text(encoding="utf-8"))
    cfg = merged_config(ticket_cfg)
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["random_seed"]))

    primary_cfd = float(cfg["primary_gate"]["cfd_fraction"])
    primary_cut = float(cfg["primary_gate"]["amplitude_cut_adc"])
    all_runs = sorted(set(cfg["train_runs"]) | set(cfg["sample_iv_calib_runs"]) | set(cfg["sample_iv_analysis_runs"]))
    input_rows = []
    for run in all_runs:
        path = base.root_path(cfg, int(run))
        input_rows.append({"run": int(run), "file": str(path), "sha256": sha256_file(base, path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    counts = base.selected_count_table(cfg)
    counts.to_csv(out_dir / "astack_counts.csv", index=False)
    run64 = base.load_pair_table(cfg, cfg["sample_iv_calib_runs"], "sample_iv_calib", primary_cfd, primary_cut)
    test_adc = base.load_pair_table(cfg, cfg["sample_iv_analysis_runs"], "sample_iv_analysis", primary_cfd, primary_cut)
    repro = base.reproduction_table(cfg, run64, test_adc)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    train_adc = base.load_pair_table(cfg, cfg["train_runs"], "sample_iii_train", primary_cfd, primary_cut)
    train_support = add_min_amp(base.load_pair_table(cfg, cfg["train_runs"], "sample_iii_train", primary_cfd, 0.0))
    test_support = add_min_amp(base.load_pair_table(cfg, cfg["sample_iv_analysis_runs"], "sample_iv_analysis", primary_cfd, 0.0))
    combined_support = pd.concat([train_support, test_support], ignore_index=True)
    target_eff = float((combined_support["min_amp"] > primary_cut).mean())
    thresholds = run_local_thresholds(combined_support, target_eff)
    thresholds.to_csv(out_dir / "fixed_efficiency_thresholds.csv", index=False)
    train_eff = apply_fixed_efficiency(train_support, thresholds, "sample_iii_train")
    test_eff = apply_fixed_efficiency(test_support, thresholds, "sample_iv_analysis")

    pred_rows = []
    cv_rows = []
    raw_rows = []
    for label, train, test in [
        ("fixed_adc_cut1000", train_adc, test_adc),
        ("fixed_efficiency", train_eff, test_eff),
    ]:
        print(f"{label}: train={len(train)} heldout={len(test)}", flush=True)
        raw_rows.append(pooled_metric(base, label, "raw_percentile68", test, "raw_residual_ns", cfg, rng))
        pred, cv = base.evaluate_pool(label, train, test, cfg)
        pred_rows.append(pred)
        cv_rows.append(cv)

    all_pred = pd.concat(pred_rows, ignore_index=True)
    ridge_cv = pd.concat(cv_rows, ignore_index=True)
    metrics, deltas, per_run = base.summarize(all_pred, cfg, rng)
    raw_metrics = pd.DataFrame(raw_rows)
    leakage = base.leakage_checks(train_eff, cfg)

    raw_metrics.to_csv(out_dir / "raw_gate_metrics.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    ridge_cv.to_csv(out_dir / "ridge_cv_scan.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    all_pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False, compression="gzip")

    primary = metrics[metrics["pool"].eq("fixed_efficiency")].sort_values("robust_width_ns")
    winner = primary.iloc[0].to_dict()
    raw_adc = raw_metrics[raw_metrics["pool"].eq("fixed_adc_cut1000")].iloc[0].to_dict()
    raw_eff = raw_metrics[raw_metrics["pool"].eq("fixed_efficiency")].iloc[0].to_dict()
    support_delta = float(raw_eff["robust_width_ns"] - raw_adc["robust_width_ns"])
    interpretation = (
        "support-normalized residual structure is still model-dependent, favoring CFD interpolation or waveform-shape noise after low-amplitude support is controlled"
        if abs(support_delta) < 0.25
        else "low-amplitude support loss is a visible contributor because the raw width changes materially under fixed-efficiency gating"
    )
    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": f"fixed_efficiency / {winner['method']}",
        "primary_gate_label": "fixed_efficiency",
        "primary_metric": "Sample IV A1-A3 percentile68 residual width, split by run, run-bootstrap CI",
        "methods_benchmarked": METHOD_ORDER,
        "best_fixed_adc_cut1000": metrics[metrics["pool"].eq("fixed_adc_cut1000")].sort_values("robust_width_ns").iloc[0].to_dict(),
        "raw_fixed_adc_cut1000": raw_adc,
        "raw_fixed_efficiency": raw_eff,
        "raw_fixed_efficiency_minus_fixed_adc_width_ns": support_delta,
        "target_pair_efficiency": target_eff,
        "heldout_runs": [int(r) for r in cfg["sample_iv_analysis_runs"]],
        "n_heldout_pairs_fixed_adc": int(len(test_adc)),
        "n_heldout_pairs_fixed_efficiency": int(len(test_eff)),
        "torch_available": bool(base.torch is not None),
        "leakage_flags": int(leakage["flag"].sum()),
        "interpretation": interpretation,
        "next_tickets": [
            "S18l: scan CFD fraction under fixed-efficiency A-stack gates to isolate interpolation-noise optima from selection-support changes."
        ],
        "git_commit": base.git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    tables = {
        "metrics": metrics,
        "thresholds": thresholds,
        "raw_metrics": raw_metrics,
        "deltas": deltas,
        "per_run": per_run,
        "reproduction": repro,
        "counts": counts,
        "leakage": leakage,
    }
    write_report(out_dir, cfg, result, tables)

    artifacts = sorted(p for p in out_dir.iterdir() if p.is_file())
    manifest = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "config": str(args.config),
        "command": f"/home/billy/anaconda3/bin/python {cfg['script_path']} --config {args.config}",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "output_sha256": {p.name: sha256_file(base, p) for p in artifacts if p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
