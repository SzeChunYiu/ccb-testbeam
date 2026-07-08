#!/usr/bin/env python3
"""S02l dynamic-only timing quarantine boundary benchmark.

This study reuses the S02j run-heldout timing scaffold but changes the
question layer to the dynamic-only selector boundary.  The raw ROOT count gate
is still executed first; the benchmark compares the strong no-proxy traditional
timewalk refit, a transparent dynamic-boundary quarantine proxy, and guarded
ridge/HGB/MLP/1D-CNN/gated-NN alternatives.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02e_current_rate_drift_timewalk as s02e
import s02j_1781061044_485_7c697079_root_only_rate_proxy_falsification_ledger as s02j


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def md_table(df: pd.DataFrame, cols: Sequence[str], n: int | None = None) -> str:
    view = df.loc[:, list(cols)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def append_dynamic_only_reproduction(match: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Append the S00c dynamic-range-only raw ROOT selector anchor."""

    baseline_idx = [int(i) for i in config["baseline_samples"]]
    channels = np.asarray([int(ch) for ch in config["staves"].values()])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    dynamic_only = 0

    for run in s02.configured_runs(config):
        for batch in s02.iter_raw(s02.raw_file(config, int(run)), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            median_amp = waveforms.max(axis=-1) - baseline
            dynamic_amp = waveforms.max(axis=-1) - waveforms.min(axis=-1)
            dynamic_only += int(((dynamic_amp > cut) & ~(median_amp > cut)).sum())

    expected = int(config["expected_counts"]["dynamic_only"])
    row = {
        "quantity": "dynamic_only",
        "report_value": expected,
        "reproduced": int(dynamic_only),
        "delta": int(dynamic_only) - expected,
        "tolerance": 0,
        "pass": int(dynamic_only) == expected,
    }
    return pd.concat([match, pd.DataFrame([row])], ignore_index=True)


def support_shift_summary(pairs: pd.DataFrame, per_run: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = pairs[pairs["method"] == "traditional_global_no_proxy"].copy()
    for method, sub in pairs.groupby("method", sort=True):
        retained = sub.groupby("heldout_run")["event_id"].nunique()
        base_retained = base.groupby("heldout_run")["event_id"].nunique().reindex(retained.index)
        amp_shift = []
        for run, group in sub.groupby("heldout_run"):
            b = base[base["heldout_run"] == run]
            if len(group) and len(b):
                amp_shift.append(abs(float(group["amplitude_mean_adc"].mean()) - float(b["amplitude_mean_adc"].mean())))
        metric = per_run[per_run["method"] == method]
        rows.append(
            {
                "method": method,
                "family": str(sub["family"].iloc[0]),
                "mean_retained_fraction": float((retained / base_retained).mean()),
                "min_retained_fraction": float((retained / base_retained).min()),
                "support_shift_energy_distance_adc": float(np.mean(amp_shift)) if amp_shift else 0.0,
                "mean_full_rms_ns": float(metric["full_rms_ns"].mean()) if len(metric) else float("nan"),
                "mean_tail_frac_abs_gt5ns": float(metric["tail_frac_abs_gt5ns"].mean()) if len(metric) else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "method"])


def dynamic_quarantine_table(run_boot: pd.DataFrame) -> pd.DataFrame:
    baseline = run_boot[run_boot["method"] == "traditional_global_no_proxy"].iloc[0]
    rows = []
    for _, row in run_boot.iterrows():
        method = str(row["method"])
        if method == "traditional_global_no_proxy":
            policy = "median-first timing refit, no dynamic quarantine"
        elif method == "traditional_proxy_dynamic_boundary":
            policy = "transparent matched dynamic-boundary abstention/refit"
        elif row["family"] == "ml":
            policy = "run-heldout calibrated selector-risk timing-tail refit"
        elif row["family"] == "shuffled_target_control":
            policy = "negative control: shuffled residual target"
        else:
            policy = "traditional nuisance refit comparator"
        rows.append(
            {
                "method": method,
                "policy": policy,
                "mean_sigma68_ns": float(row["mean_sigma68_ns"]),
                "ci_low": float(row["ci_low"]),
                "ci_high": float(row["ci_high"]),
                "lift_vs_traditional_ns": float(baseline["mean_sigma68_ns"] - row["mean_sigma68_ns"]),
                "lift_ci_low": float(-row["delta_ci_high"]),
                "lift_ci_high": float(-row["delta_ci_low"]),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def write_report(out_dir: Path, config: dict, result: dict, match: pd.DataFrame, reproduction: pd.DataFrame, cov: pd.DataFrame, per_run: pd.DataFrame, run_boot: pd.DataFrame, quarantine: pd.DataFrame, support: pd.DataFrame, leakage: pd.DataFrame, model_info: pd.DataFrame) -> None:
    nominal = run_boot[~run_boot["family"].eq("shuffled_target_control")].copy()
    ml_rows = nominal[nominal["family"].eq("ml")].sort_values("mean_sigma68_ns")
    trad_rows = nominal[nominal["family"].str.startswith("traditional", na=False)].sort_values("mean_sigma68_ns")
    controls = run_boot[run_boot["family"].eq("shuffled_target_control")].copy()
    md = f"""# S02l: dynamic-only timing quarantine boundary

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Abstract

This study asks whether pulses admitted only by the dynamic-range selector can be safely quarantined, or whether such an abstention erodes legitimate timing support.  The analysis starts from raw B-stack ROOT, reproduces the S00c selector count including the `dynamic_only` count, and then performs a leave-one-run-out Sample-II timing benchmark.  The compared methods are a strong traditional median-first template/timewalk refit, a transparent dynamic-boundary traditional quarantine proxy, ridge regression, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated proxy network.  Confidence intervals are run-block bootstraps across held-out runs.

## Raw ROOT Reproduction

The script reads `{config['raw_root_dir']}` directly before model fitting.  The accepted selector is

`max(HRDv - median(HRDv[0:4])) > 1000 ADC`,

and the dynamic-only comparator is

`max(HRDv) - min(HRDv) > 1000 ADC` while the median-first selector is false.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

Reference timing anchors were also rebuilt from raw-derived pulses:

{md_table(reproduction, ['quantity', 'heldout_run', 'reproduced_sigma68_ns', 'reference_sigma68_ns', 'delta_ns', 'pass'])}

## Estimands and Equations

For event `e`, method `m`, and downstream staves `a,b in {{B4,B6,B8}}`, the paired timing residual is

`r_ab(e;m) = [t_a(e;m) - z_a/v] - [t_b(e;m) - z_b/v]`,

where `z` is the 2 cm stave coordinate and `1/v = 0.078 ns/cm`.  The robust width is

`sigma68(m) = (Q_0.84(r_ab) - Q_0.16(r_ab)) / 2`.

The full RMS and tail metric are

`RMS(m) = sqrt(mean((r_ab - mean(r_ab))^2))`,

`T_5(m) = mean(|r_ab - median(r_ab)| > 5 ns)`.

The quarantine lift is defined as

`L(m) = sigma68(traditional_global_no_proxy) - sigma68(m)`;

positive lift means the method narrows the downstream timing closure relative to the strong traditional baseline.

## Split and Features

Runs `{', '.join(str(x) for x in config['timing']['loro_runs'])}` are held out one at a time.  Fold-local preprocessing never sees the held-out run.  Features are pre-label ROOT/run summaries and downstream stave indicators; event ids, pair residuals, target timing labels, and held-out rows are excluded from fitting.

Pre-label run covariates:

{md_table(cov[['run', 'current_nA', 'trigger_entry_density', 'entries_per_eventno', 'selected_multiplicity_per_event', 'downstream_allhit_fraction']].drop_duplicates().sort_values('run'), ['run', 'current_nA', 'trigger_entry_density', 'entries_per_eventno', 'selected_multiplicity_per_event', 'downstream_allhit_fraction'])}

## Methods

The strong traditional method is `traditional_global_no_proxy`, the established global template/timewalk refit without dynamic quarantine.  The primary traditional quarantine comparator is `traditional_proxy_dynamic_boundary`, which uses trigger-density, selected-multiplicity, and all-hit topology covariates as a matched dynamic-boundary abstention/refit proxy.  Additional traditional nuisance refits are included as systematics.

ML/NN models use the same allowed pre-label feature family:

- `ml_ridge_all_root_proxies`: standardized ridge regression with grouped-run CV over alpha.
- `ml_hgb_all_root_proxies`: histogram gradient-boosted trees.
- `ml_mlp_all_root_proxies`: feed-forward MLP.
- `ml_cnn1d_proxy_all_root_proxies`: compact 1D-CNN over the ordered proxy vector.
- `ml_gated_proxy_all_root_proxies`: new gated architecture combining linear and nonlinear branches.

Model audit:

{md_table(model_info, ['heldout_run', 'model', 'proxy_family', 'n_train_pulses', 'n_features', 'feature_policy'], n=60)}

## Results

Run-block benchmark:

{md_table(nominal, ['method', 'family', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high', 'mean_full_rms_ns', 'mean_tail_frac_abs_gt5ns'], n=40)}

Dynamic quarantine ranking:

{md_table(quarantine, ['method', 'policy', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'lift_vs_traditional_ns', 'lift_ci_low', 'lift_ci_high'], n=40)}

Per-run event-bootstrap metrics:

{md_table(per_run[~per_run['family'].eq('shuffled_target_control')].sort_values(['heldout_run', 'sigma68_ns']), ['heldout_run', 'method', 'family', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'tail_frac_abs_gt5ns'], n=120)}

ML/NN-only ranking:

{md_table(ml_rows, ['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'], n=20)}

Traditional/systematic ranking:

{md_table(trad_rows, ['method', 'family', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'], n=20)}

Retained-fraction and support-shift ledger:

{md_table(support, ['method', 'family', 'mean_retained_fraction', 'min_retained_fraction', 'support_shift_energy_distance_adc', 'mean_full_rms_ns', 'mean_tail_frac_abs_gt5ns'], n=60)}

## Controls, Systematics, and Caveats

Leakage ledger:

{md_table(leakage, ['heldout_run', 'check', 'value', 'pass'], n=160)}

Shuffled-target controls:

{md_table(controls, ['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns'], n=20)}

Systematics:

- Dynamic-only is a selector-semantics label, not a hardware truth label; the quarantine boundary is therefore evaluated as a timing-support decision, not as particle identification.
- The dynamic-boundary traditional comparator uses pre-label run/topology covariates to approximate matched abstention.  It is intentionally transparent but cannot prove causal removal of all dynamic-only pathologies.
- The 1D-CNN is applied to ordered proxy features, not raw waveform samples; this prevents leakage from downstream timing labels but limits architecture expressivity.
- Run 65 remains sparse; the run-block CI is the headline interval and pooled event CIs are treated as secondary diagnostics.
- A method that wins while its shuffled-target control is competitive should be considered a false-improvement warning.

## Verdict

Winner named in `result.json`: `{result['winner']['method']}` with run-block mean `sigma68 = {result['winner']['mean_sigma68_ns']:.3f} ns` and 95% CI `[{result['winner']['ci'][0]:.3f}, {result['winner']['ci'][1]:.3f}] ns`.

{result['verdict']}

No novel follow-up ticket is appended.  The remaining uncertainty is systematic interpretation of the selector boundary, not a missing computational benchmark.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02l_1781081167_631_051f65df_dynamic_only_timing_quarantine_boundary.json")
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = Path(args.config)
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = append_dynamic_only_reproduction(s02.reproduce_counts(config), config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    all_pulses = s02j.load_loro_pulses(config)
    all_pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index().to_csv(out_dir / "loro_pulse_counts_by_run.csv", index=False)

    cov_cfg = copy.deepcopy(config)
    cov_cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cov_cfg["timing"]["heldout_runs"] = []
    raw_covariates = s02e.raw_run_covariates(cov_cfg)
    raw_covariates.to_csv(out_dir / "run_covariates_raw_pretiming.csv", index=False)

    folds = [s02j.run_fold(all_pulses, config, int(run), raw_covariates, rng) for run in config["timing"]["loro_runs"]]
    pairs = pd.concat([x["pairs"] for x in folds], ignore_index=True)
    per_run = pd.concat([x["per_run"] for x in folds], ignore_index=True)
    leakage = pd.concat([x["leakage"] for x in folds], ignore_index=True)
    cov = pd.concat([x["run_covariates"] for x in folds], ignore_index=True)
    model_info = pd.concat([x["model_info"] for x in folds], ignore_index=True)
    run_boot = s02j.run_block_bootstrap(per_run, config)
    reproduction = s02j.reproduction_reference_table(config, per_run)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("reference reproduction failed")

    support = support_shift_summary(pairs, per_run)
    quarantine = dynamic_quarantine_table(run_boot)

    pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_bootstrap_metrics.csv", index=False)
    run_boot.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    quarantine.to_csv(out_dir / "dynamic_quarantine_lift_table.csv", index=False)
    support.to_csv(out_dir / "retained_support_shift_table.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cov.to_csv(out_dir / "run_covariates_prelabel_by_fold.csv", index=False)
    model_info.to_csv(out_dir / "model_audit.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    hashes = s02j.input_hashes(config)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = run_boot[~run_boot["family"].eq("shuffled_target_control")].copy()
    winner = nominal.sort_values("mean_sigma68_ns").iloc[0]
    baseline = run_boot[run_boot["method"] == "traditional_global_no_proxy"].iloc[0]
    dynamic = run_boot[run_boot["method"] == "traditional_proxy_dynamic_boundary"].iloc[0]
    best_ml = run_boot[run_boot["family"] == "ml"].sort_values("mean_sigma68_ns").iloc[0]
    shuffled_failures = int((leakage[leakage["check"].str.startswith("shuffled_target", na=False)]["pass"] == False).sum())
    verdict = (
        f"The strong traditional baseline has mean sigma68 {float(baseline['mean_sigma68_ns']):.3f} ns. "
        f"The dynamic-boundary traditional quarantine proxy has mean sigma68 {float(dynamic['mean_sigma68_ns']):.3f} ns "
        f"(lift {float(baseline['mean_sigma68_ns'] - dynamic['mean_sigma68_ns']):+.3f} ns). "
        f"The best ML/NN method is {best_ml['method']} at {float(best_ml['mean_sigma68_ns']):.3f} ns. "
    )
    if str(winner["method"]) == "traditional_proxy_dynamic_boundary":
        verdict += "The transparent dynamic-boundary quarantine is the nominal winner and is preferred because it is simpler than the ML/NN alternatives."
    elif str(winner["family"]) == "ml":
        verdict += "An ML/NN method wins numerically; adoption should remain conditional on the shuffled-target and leakage controls."
    else:
        verdict += "The dynamic-only quarantine does not beat the strongest traditional timing refit in this run-heldout benchmark."
    if shuffled_failures:
        verdict += f" {shuffled_failures} shuffled-target control checks are warnings."

    result = {
        "study": "S02l",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(x) for x in config["timing"]["loro_runs"]],
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "mean_sigma68_ns": float(winner["mean_sigma68_ns"]),
            "ci": [float(winner["ci_low"]), float(winner["ci_high"])],
            "delta_vs_traditional_ns": float(winner["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner["delta_ci_low"]), float(winner["delta_ci_high"])],
        },
        "traditional_baseline": {
            "method": "traditional_global_no_proxy",
            "mean_sigma68_ns": float(baseline["mean_sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "dynamic_boundary_traditional": {
            "method": "traditional_proxy_dynamic_boundary",
            "mean_sigma68_ns": float(dynamic["mean_sigma68_ns"]),
            "ci": [float(dynamic["ci_low"]), float(dynamic["ci_high"])],
            "lift_vs_traditional_ns": float(baseline["mean_sigma68_ns"] - dynamic["mean_sigma68_ns"]),
        },
        "best_ml_nn": {
            "method": str(best_ml["method"]),
            "mean_sigma68_ns": float(best_ml["mean_sigma68_ns"]),
            "ci": [float(best_ml["ci_low"]), float(best_ml["ci_high"])],
            "delta_vs_traditional_ns": float(best_ml["delta_vs_traditional_ns"]),
        },
        "controls": {
            "shuffled_target_failures": shuffled_failures,
            "structural_guards_pass": bool(leakage[~leakage["check"].str.startswith("shuffled_target", na=False)]["pass"].all()),
        },
        "next_tickets": [],
        "verdict": verdict,
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, result, match, reproduction, cov, per_run, run_boot, quarantine, support, leakage, model_info)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02l",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(cfg_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": s02j.hash_outputs(out_dir),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
