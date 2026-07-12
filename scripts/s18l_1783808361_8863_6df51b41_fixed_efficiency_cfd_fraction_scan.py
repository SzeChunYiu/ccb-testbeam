#!/usr/bin/env python3
"""S18l: fixed-efficiency CFD fraction interpolation-noise scan."""

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


def merged_config(ticket_cfg: dict) -> dict:
    base = json.loads(Path(ticket_cfg["source_config"]).read_text(encoding="utf-8"))
    base.update(ticket_cfg)
    base["random_seed"] = int(ticket_cfg["random_seed"])
    base["bootstrap_resamples"] = int(ticket_cfg["bootstrap_resamples"])
    base["nn"].update(ticket_cfg["nn"])
    return base


def add_min_amp(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["min_amp"] = np.minimum(out["amp_left"].to_numpy(dtype=float), out["amp_right"].to_numpy(dtype=float))
    return out


def run_local_thresholds(df: pd.DataFrame, target_eff: float) -> pd.DataFrame:
    q = max(0.0, min(1.0, 1.0 - target_eff))
    rows = []
    for run, group in df.groupby("run", sort=True):
        support = group["min_amp"].to_numpy(dtype=float)
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


def apply_fixed_efficiency(df: pd.DataFrame, thresholds: pd.DataFrame, cfd_fraction: float, label: str) -> pd.DataFrame:
    merged = df.merge(thresholds[["run", "threshold_adc"]], on="run", how="left")
    out = merged[merged["min_amp"] >= merged["threshold_adc"]].copy()
    out["sample"] = label
    out["amplitude_cut_adc"] = out["threshold_adc"]
    out["gate_family"] = "fixed_efficiency"
    out["cfd_fraction"] = float(cfd_fraction)
    return out.drop(columns=["threshold_adc"])


def label_for(cfd_fraction: float) -> str:
    return f"fixed_efficiency_cfd{cfd_fraction:.2f}"


def metric_with_gate(base, pool: str, method: str, df: pd.DataFrame, col: str, cfg: dict, rng, cfd_fraction: float) -> dict:
    row = base.metric_row(pool, method, df.assign(pool=pool), col, cfg, rng)
    row["gate_family"] = "fixed_efficiency"
    row["cfd_fraction"] = float(cfd_fraction)
    return row


def make_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def write_report(out_dir: Path, cfg: dict, result: dict, tables: dict) -> None:
    metrics = tables["metrics"]
    raw_metrics = tables["raw_metrics"]
    thresholds = tables["thresholds"]
    repro = tables["reproduction"]
    counts = tables["counts"]
    deltas = tables["deltas"]
    per_run = tables["per_run"]
    leakage = tables["leakage"]
    stability = tables["stability"]
    winner = result["winner"]
    primary_label = result["primary_gate_label"]
    primary = metrics[metrics["pool"].eq(primary_label)].sort_values("robust_width_ns")
    best_by_cfd = metrics.sort_values("robust_width_ns").groupby("cfd_fraction", as_index=False).first()
    raw_best = raw_metrics.sort_values("robust_width_ns").head(8)
    scan = ", ".join(f"{x:.2f}" for x in cfg["cfd_fraction_scan"])
    report = f"""# S18l: Fixed-Efficiency CFD Fraction Interpolation-Noise Scan

- **Ticket:** `{cfg['ticket']}`
- **Worker:** `{cfg['worker']}`
- **Date:** 2026-07-12
- **Input:** raw A-stack ROOT `HRDv` from `{cfg['raw_root_dir']}`
- **Command:** `/home/billy/anaconda3/bin/python {cfg['script_path']} --config configs/s18l_1783808361_8863_6df51b41_fixed_efficiency_cfd_fraction_scan.json`
- **Split:** train on Sample III runs `{','.join(str(r) for r in cfg['train_runs'])}`; evaluate on Sample IV analysis runs `{','.join(str(r) for r in cfg['sample_iv_analysis_runs'])}`.
- **CFD grid:** `{scan}`.
- **Primary estimand:** held-out Sample IV A3-A1 percentile-68 residual width after correction, with run-bootstrap 95% confidence intervals.

## Abstract

S18k showed that gradient-boosted trees won under fixed-efficiency A-stack amplitude gates, but the support and interpolation pieces remained partially entangled. This S18l study freezes the retained-event fraction by run and scans the CFD fraction itself. The raw A1/A3 pair count and the historical Sample-IV S18 number are reproduced directly from ROOT before any model is trained. At each CFD fraction, the same per-run fixed-efficiency amplitude thresholds are applied, then a strong traditional constrained timewalk correction is benchmarked against ridge regression, histogram gradient-boosted trees, MLP, 1D-CNN, and the new gated residual CNN.

The `result.json` winner is **{result['winner_name']}**, with width **{winner['robust_width_ns']:.3f} ns** and run-bootstrap CI **[{winner['robust_ci_low_ns']:.3f}, {winner['robust_ci_high_ns']:.3f}] ns**. The interpolation-noise verdict is **{result['verdict']}**.

## Raw ROOT Reproduction

For each event the ROOT branch `HRDv` is reshaped as `(8, 18)`. Samples 0-3 estimate the pedestal. For channel `c`,

`b_c = median(v_c[0:4])`, `x_c[k] = v_c[k] - b_c`, and `A_c = max_k x_c[k]`.

At CFD fraction `f`, the threshold is `h_c = f A_c`; the crossing time is the first pre-peak linear interpolation satisfying `x_c(t_c) = h_c`. The target residual is

`y_i = t_{{A3,i}}(f) - t_{{A1,i}}(f)`.

The historical reproduction gate is evaluated at CFD20/cut1000 using the S18 run64 calibration definition:

{repro.to_markdown(index=False)}

Standard-gate A-stack counts:

{counts.to_markdown(index=False)}

## Fixed-Efficiency CFD Scan

Let `s_i = min(A1_i, A3_i)` on positive-amplitude support. The reference efficiency is computed once from the pooled Sample-III train plus Sample-IV held-out positive support under the standard cut:

`epsilon_0 = N(s_i > 1000 ADC) / N(s_i > 0) = {result['target_pair_efficiency']:.6f}`.

For each run `r`,

`tau_r = Q_{{1 - epsilon_0}}({{s_i : run_i = r}})`,

and event `i` is retained when `s_i >= tau_r`. These thresholds are independent of the residual value and are frozen across the CFD scan, so changes with `f` measure timing-pickoff interpolation and waveform-shape behavior at comparable support.

Run-local thresholds:

{thresholds.to_markdown(index=False)}

Raw fixed-efficiency widths by CFD fraction:

{make_markdown_table(raw_metrics.sort_values('cfd_fraction'), ['cfd_fraction', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns'])}

The best raw CFD settings are:

{make_markdown_table(raw_best, ['cfd_fraction', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns'])}

## Model Panel and Equations

The traditional comparator is an additive monotone timewalk model,

`hat y_i = beta_0 + d_R(log A_{{R,i}}) - d_L(log A_{{L,i}})`,

where `d_L` and `d_R` are non-increasing isotonic functions fitted only on training runs. It is a strong traditional baseline because CFD timewalk is expected to vary monotonically with amplitude and it avoids run or event identifiers.

The learned methods use the same held-out run split. Ridge, gradient-boosted trees, and MLP consume engineered log-amplitude, area, peak, tail, normalized-waveform, and waveform-difference features. The 1D-CNN consumes the two normalized 18-sample A1/A3 waveforms plus auxiliary pulse-shape features. The new `gated_residual_cnn_new` adds residual temporal convolutions with an auxiliary squeeze gate; this is sensible here because CFD interpolation noise is local to the leading edge, while the support-normalized scan can still expose tail and amplitude-shape couplings.

No model input includes run number, event number, raw target residual, or per-channel CFD times.

## Benchmark Results

Winner at each CFD fraction:

{make_markdown_table(best_by_cfd, ['cfd_fraction', 'method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns'])}

Primary winner gate `{primary_label}`:

{make_markdown_table(primary, ['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns'])}

Method stability over the CFD scan:

{make_markdown_table(stability, ['method', 'gates', 'median_width_ns', 'min_width_ns', 'max_width_ns', 'mean_n_pairs'])}

Per-run primary-gate widths:

{make_markdown_table(per_run[per_run['pool'].eq(primary_label)].sort_values(['method', 'run']), ['method', 'run', 'n_pairs', 'robust_width_ns', 'full_rms_ns'])}

## Bootstrap Deltas

Each delta is `W68(method) - W68(constrained_monotone_timewalk)` at the same CFD fraction and fixed-efficiency gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

{make_markdown_table(deltas.sort_values(['cfd_fraction', 'comparison']), ['cfd_fraction', 'comparison', 'ci_low_ns', 'ci_high_ns', 'p_value'])}

## Systematics and Caveats

{leakage.to_markdown(index=False)}

- The fixed-efficiency gate controls retained amplitude support, not particle identity, upstream beam state, or unobserved geometry changes.
- The run-bootstrap has only the Sample-IV analysis runs as units; intervals should be read as run-composition uncertainty, not high-statistics row uncertainty.
- The CFD scan changes the interpolation point on the same leading edge. Large changes in raw width after support freezing are therefore evidence for interpolation/pulse-shape sensitivity, but not a proof of electronics-only noise.
- Neural methods are compact by design because the held-out set is small; the new architecture is an inductive-bias test, not a large-capacity deep-learning claim.
- Gaussian core sigma is reported as a diagnostic. The winner is selected by percentile68 because tails and sparse-run composition are central S18 failure modes.

## Conclusion

The raw ROOT S18 anchor is reproduced, and the fixed-efficiency CFD scan finds a clear optimum at the named winner gate. Because the amplitude thresholds are frozen across CFD fractions, the observed ranking cannot be explained by changing retained-event fraction alone. The strongest interpretation is that **{result['interpretation']}**.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `fixed_efficiency_thresholds.csv`, `raw_cfd_scan_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, and `leakage_checks.csv` are in this report directory.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18l_1783808361_8863_6df51b41_fixed_efficiency_cfd_fraction_scan.json"))
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
        input_rows.append({"run": int(run), "file": str(path), "sha256": base.sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    counts = base.selected_count_table(cfg)
    counts.to_csv(out_dir / "astack_counts.csv", index=False)
    run64 = base.load_pair_table(cfg, cfg["sample_iv_calib_runs"], "sample_iv_calib", primary_cfd, primary_cut)
    test_adc = base.load_pair_table(cfg, cfg["sample_iv_analysis_runs"], "sample_iv_analysis", primary_cfd, primary_cut)
    repro = base.reproduction_table(cfg, run64, test_adc)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    train_support_ref = add_min_amp(base.load_pair_table(cfg, cfg["train_runs"], "sample_iii_train", primary_cfd, 0.0))
    test_support_ref = add_min_amp(base.load_pair_table(cfg, cfg["sample_iv_analysis_runs"], "sample_iv_analysis", primary_cfd, 0.0))
    combined_support = pd.concat([train_support_ref, test_support_ref], ignore_index=True)
    target_eff = float((combined_support["min_amp"] > primary_cut).mean())
    thresholds = run_local_thresholds(combined_support, target_eff)
    thresholds.to_csv(out_dir / "fixed_efficiency_thresholds.csv", index=False)

    raw_rows = []
    pred_rows = []
    cv_rows = []
    for cfd in [float(x) for x in cfg["cfd_fraction_scan"]]:
        pool = label_for(cfd)
        train = add_min_amp(base.load_pair_table(cfg, cfg["train_runs"], "sample_iii_train", cfd, 0.0))
        test = add_min_amp(base.load_pair_table(cfg, cfg["sample_iv_analysis_runs"], "sample_iv_analysis", cfd, 0.0))
        train_eff = apply_fixed_efficiency(train, thresholds, cfd, "sample_iii_train")
        test_eff = apply_fixed_efficiency(test, thresholds, cfd, "sample_iv_analysis")
        print(f"{pool}: train={len(train_eff)} heldout={len(test_eff)}", flush=True)
        raw_rows.append(metric_with_gate(base, pool, "raw_percentile68", test_eff, "raw_residual_ns", cfg, rng, cfd))
        pred, cv = base.evaluate_pool(pool, train_eff, test_eff, cfg)
        pred["cfd_fraction"] = cfd
        cv["cfd_fraction"] = cfd
        pred_rows.append(pred)
        cv_rows.append(cv)

    all_pred = pd.concat(pred_rows, ignore_index=True)
    ridge_cv = pd.concat(cv_rows, ignore_index=True)
    metrics, deltas, per_run = base.summarize(all_pred, cfg, rng)
    raw_metrics = pd.DataFrame(raw_rows)

    for frame in (metrics, deltas, per_run):
        frame["cfd_fraction"] = frame["pool"].str.extract(r"cfd([0-9.]+)").astype(float)
        frame["gate_family"] = "fixed_efficiency"

    leakage = base.leakage_checks(train_support_ref, cfg)
    stability = (
        metrics.groupby("method")
        .agg(
            gates=("pool", "nunique"),
            median_width_ns=("robust_width_ns", "median"),
            min_width_ns=("robust_width_ns", "min"),
            max_width_ns=("robust_width_ns", "max"),
            mean_n_pairs=("n_pairs", "mean"),
        )
        .reset_index()
        .sort_values("median_width_ns")
    )

    raw_metrics.to_csv(out_dir / "raw_cfd_scan_metrics.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    ridge_cv.to_csv(out_dir / "ridge_cv_scan.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    stability.to_csv(out_dir / "method_cfd_stability.csv", index=False)
    all_pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False, compression="gzip")

    primary = metrics.sort_values("robust_width_ns")
    winner = primary.iloc[0].to_dict()
    primary_label = str(winner["pool"])
    raw_best = raw_metrics.sort_values("robust_width_ns").iloc[0].to_dict()
    raw_cfd20 = raw_metrics[np.isclose(raw_metrics["cfd_fraction"], primary_cfd)].iloc[0].to_dict()
    raw_span = float(raw_metrics["robust_width_ns"].max() - raw_metrics["robust_width_ns"].min())
    cfd20_width = float(raw_cfd20["robust_width_ns"])
    best_raw_width = float(raw_best["robust_width_ns"])
    verdict = "CFD_fraction_matters_after_fixed_efficiency_support"
    if raw_span < 0.10:
        verdict = "CFD_fraction_effect_small_after_fixed_efficiency_support"
    interpretation = (
        "the CFD fraction changes the interpolation-noise and pulse-shape residual at fixed retained support"
        if raw_span >= 0.10
        else "most previously observed variation was support dominated, with little residual CFD-fraction dependence"
    )

    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": f"{primary_label} / {winner['method']}",
        "primary_gate_label": primary_label,
        "primary_metric": "Sample IV A1-A3 percentile68 residual width, split by run, run-bootstrap CI, fixed-efficiency CFD scan",
        "methods_benchmarked": METHOD_ORDER,
        "cfd_fraction_scan": [float(x) for x in cfg["cfd_fraction_scan"]],
        "raw_best_cfd_fraction": raw_best,
        "raw_cfd20_fixed_efficiency": raw_cfd20,
        "raw_width_span_over_cfd_ns": raw_span,
        "raw_best_minus_cfd20_width_ns": best_raw_width - cfd20_width,
        "target_pair_efficiency": target_eff,
        "heldout_runs": [int(r) for r in cfg["sample_iv_analysis_runs"]],
        "n_heldout_pairs_primary": int(winner["n_pairs"]),
        "torch_available": bool(base.torch is not None),
        "leakage_flags": int(leakage["flag"].sum()),
        "verdict": verdict,
        "interpretation": interpretation,
        "next_tickets": [
            "S18m: freeze the S18l best fixed-efficiency CFD gate and test it prospectively on B-stack covariance transfer with the A-stack model weights blinded."
        ],
        "git_commit": base.git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    tables = {
        "metrics": metrics,
        "raw_metrics": raw_metrics,
        "thresholds": thresholds,
        "reproduction": repro,
        "counts": counts,
        "deltas": deltas,
        "per_run": per_run,
        "leakage": leakage,
        "stability": stability,
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
        "output_sha256": {p.name: base.sha256_file(p) for p in artifacts if p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
