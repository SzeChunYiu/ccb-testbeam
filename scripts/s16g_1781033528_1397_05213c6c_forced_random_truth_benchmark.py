#!/usr/bin/env python3
"""S16g forced/random truth acquisition audit plus proxy benchmark fallback.

The claimed ticket asks for direct forced/random HRD pedestal truth.  The
visible ROOT bundle has no non-beam entries, so this script records that hard
gate before running the pre-registered S16f proxy benchmark as a fallback.  The
winner is therefore named for the proxy timing-tail task, not for direct
forced/random electronics truth.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_module("s16f_helpers", "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py")
S16G = load_module("s16g_helpers", "scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py")


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def acquisition_audit(config: dict, out_dir: Path) -> Dict[str, Any]:
    root_audit = S16G.audit_root_metadata(config)
    file_audit = S16G.audit_filesystem_and_archives(config)
    direct_rows = S16G.load_direct_nonbeam_entries(config)
    root_audit.to_csv(out_dir / "root_trigger_branch_audit.csv", index=False)
    file_audit.to_csv(out_dir / "file_archive_inventory.csv", index=False)
    direct_rows.to_csv(out_dir / "direct_nonbeam_entries.csv", index=False)
    strict_candidates = file_audit[
        (file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))
    ]
    return {
        "root_files_audited": int(len(root_audit)),
        "non_beam_trigger_entries": int(root_audit["non_beam_trigger_entries"].sum()),
        "files_with_tag_like_branch": int(root_audit["has_tag_like_branch"].sum()),
        "filesystem_archive_rows_audited": int(len(file_audit)),
        "strict_forced_random_root_or_archive_candidates": int(len(strict_candidates)),
        "direct_nonbeam_entries": int(len(direct_rows)),
        "missing_search_roots": file_audit[file_audit["kind"] == "missing_search_root"]["search_root"].tolist(),
    }


def write_proxy_report(out_dir: Path, config: dict, numbers: dict, acquisition: dict, result: dict) -> None:
    direct_truth = acquisition["direct_nonbeam_entries"]
    forced_status = "blocked" if direct_truth == 0 else "ready"
    report = f"""# S16g: Forced/Random HRD Pedestal Truth Acquisition With Proxy Benchmark Fallback

- **Study ID:** S16g
- **Ticket:** {config["ticket"]}
- **Author (worker label):** {config["worker"]}
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S16f pre-trigger veto benchmark, S16g forced/random acquisition audit
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `configs/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.json`

## 0. Question

Can the mounted raw HRD ROOT data support a direct forced/random no-pulse pedestal truth rerun, and, if not, which frozen quiet-vs-beam proxy method is strongest under the same Sample-II leave-one-run-out split?

The decision has two atomic gates: first audit the visible ROOT and archive mirrors for true forced/random events; second benchmark the frozen proxy task with the same run-held-out split and explicitly label it as a fallback rather than direct truth.

## 1. Reproduction (mandatory gate)

The raw-ROOT gate reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root`, subtracts the median of samples 0-3 for B2/B4/B6/B8, and counts baseline-subtracted pulses with \(A>1000\) ADC.  This independently reproduces the S00/S16 selected-pulse count.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{numbers["match_rows"]}

The forced/random acquisition gate inspected `{acquisition["root_files_audited"]}` HRDA/HRDB ROOT files and `{acquisition["filesystem_archive_rows_audited"]}` filesystem/archive rows. It found `{acquisition["strict_forced_random_root_or_archive_candidates"]}` strict forced/random ROOT/archive candidates, `{acquisition["files_with_tag_like_branch"]}` tag-like ROOT branch sets, and `{direct_truth}` B-stack non-beam entries. Thus the direct forced/random truth rerun is **{forced_status}**; in this mounted data state it is not estimable.

## 2. Traditional (non-ML) method

The fallback benchmark uses the S16f quiet-vs-beam proxy target because the direct truth sample is absent. For event pair \(i\),

\[
r_i=(t_a-x_a/v)-(t_b-x_b/v),
\]

where `t` is CFD20 time, `x` is B-stack position at `{config["spacing_cm"]}` cm spacing, and \(1/v={config["tof_per_cm_ns"]}\) ns/cm. In each leave-one-run-out fold, pair centers \(m_p\) are train-run medians and the proxy tail label is

\[
y_i = \mathbf{{1}}\left(|r_i-m_{{p(i)}}|>{config["timing"]["tail_abs_residual_ns"]}\ \mathrm{{ns}}\\right).
\]

The strong traditional score is a train-frozen empirical quantile envelope over pre-trigger-only summaries:

\[
s_i^{{trad}}=\max_j \hat F_{{j,\mathrm{{train}}}}(z_{{ij}}),
\]

where \(z_j\) are max absolute pre-trigger amplitude, peak-to-peak range, RMS, absolute slope, and last-minus-first excursion across the two staves. The threshold is selected inside the train runs only from quantiles `{config["veto"]["threshold_quantiles"]}`, with train efficiency constrained to at least `{config["veto"]["min_train_efficiency"]}`.

## 3. ML method

The benchmark includes ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pair-symmetric architecture (`siamese_cnn_meta`). All methods use Sample-II leave-one-run-out by run. Features exclude run id, event id, residuals, labels, post-trigger waveform samples, amplitude, and peak sample. Scalers, empirical distributions, neural normalizers, model fits, pair centers, and thresholds are fit only on the training runs for each held-out run.

The tabular ML methods receive pair identity and pre-trigger summaries from samples 0-3. The 1D-CNN receives only the two four-sample pre-trigger traces. The new architecture applies a shared convolutional branch separately to the two stave pre-trigger traces, concatenates both embeddings and their absolute difference, then adds the tabular pre-trigger summaries before the binary head. Ridge scans alphas `{config["models"]["ridge_alphas"]}`; the boosted tree, MLP, and NN hyperparameters are fixed in the config before held-out scoring.

## 4. Head-to-head benchmark

Primary metric: held-out post-veto proxy tail fraction \(\Pr(|r-m_p|>5\,\mathrm{{ns}}\mid\mathrm{{kept}})\). Timing efficiency, tail capture, sigma68, full RMS, AUC, AP, and Brier score are recorded as safety/diagnostic metrics. Confidence intervals bootstrap runs and then events within sampled runs.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

Winner for the fallback proxy benchmark: **{numbers["winner"]}**. The pre-veto proxy tail fraction was `{numbers["baseline_tail"]:.4f}` and the pre-veto sigma68 was `{numbers["baseline_sigma"]:.3f}` ns. Since direct forced/random truth entries are zero, `result.json` names both the direct-truth status and the proxy winner; the proxy winner must not be read as an electronics pedestal truth winner.

Per-held-out-run metrics for the proxy winner:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
{numbers["winner_fold_rows"]}

## 5. Falsification

Pre-registration: direct forced/random truth would supersede the proxy benchmark if any non-beam/tagged B-stack truth entries existed. Because the truth count is zero, the falsification test for the fallback winner is the S16f shuffled-proxy control: train each method after permuting train-run pre-trigger proxies relative to labels. A claimed method fails if its median tail-capture advantage over shuffled proxy is below -0.05 or if any train/held-out event id overlaps.

Six methods were compared, so no nominal single-method p-value is interpreted as a discovery. The fixed operational winner is the method with the smallest held-out post-veto tail fraction subject to the efficiency penalty.

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## 6. Threats to validity

Benchmark/selection: the direct truth benchmark is blocked by missing truth rows, so the fallback task answers only which proxy score best removes timing-tail pairs. The traditional baseline is not a strawman; it uses the most direct pre-trigger summary envelope and the same threshold utility as ML.

Data leakage: all splits are by run. No label-defining fields, event identifiers, run identifiers, residuals, post-trigger samples, amplitudes, or peak locations enter the ML features. The direct forced/random gate is audited before the proxy winner is named.

Metric misuse: sigma68 can improve by discarding hard events, so timing efficiency, tail capture, post-veto tail fraction, full RMS, AUC, AP, and Brier score are recorded. No fit-based chi-square is applicable because the primary estimator is a distributional veto score, not a parametric residual fit.

Post-hoc selection: the direct-truth availability gate, LORO runs, model family list, efficiency rule, threshold grid, and bootstrap plan are fixed in the config before scoring. The report names the winner only after applying that fixed rule.

Systematics and caveats: absence in the mounted mirrors is not proof the DAQ never recorded forced/random pedestals. The LUNARC canonical path was not mounted locally if listed in `missing_search_roots`. The proxy target is a timing-tail label, not a physical contamination or electronics pedestal truth label. Pair residuals share events; CIs therefore bootstrap at run and event levels rather than individual pair rows.

## 7. Provenance manifest

`manifest.json` records the command, config, git commit, Python/platform metadata, input checksums, random seed, and output checksums. The raw ROOT checksums are in `input_sha256.csv`.

## 8. Findings & next steps

Direct forced/random S16g truth is blocked in the mounted data: `direct_nonbeam_entries = {direct_truth}` and no strict forced/random ROOT/archive candidate was visible. The fallback proxy benchmark still separates methods under the same Sample-II LORO protocol; **{numbers["winner"]}** is the strongest proxy scorer by post-veto tail fraction.

Hypothesis: the current laptop mirror contains only beam-trigger HRD runs, while forced/random pedestal acquisitions, if they exist, live in an unmounted DAQ/archive tier or were never converted into the reduced HRD ROOT bundle. The most informative next experiment is to audit external run logs or archived DAQ products before spending more effort on proxy modeling.

Queued follow-up in `result.json`: `{config["next_tickets"][0]["title"]}`. Expected information gain: it determines whether direct no-proxy pedestal closure is feasible from external acquisition provenance or must be retired as unavailable.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.py --config configs/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `root_trigger_branch_audit.csv`, `file_archive_inventory.csv`, `direct_nonbeam_entries.csv`, `sample_ii_pair_table.csv.gz`, `fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`, `head_to_head_benchmark.csv`, `bootstrap_cis.csv`, `leakage_checks.csv`, `fig_head_to_head_tail_fraction.png`, and `fig_winner_residuals_kept_vetoed.png`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    match = S16F.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    acquisition = acquisition_audit(config, out_dir)
    direct_truth_ready = acquisition["direct_nonbeam_entries"] > 0

    pulses = S16F.load_sample_ii_pulses(config)
    pair_frame = S16F.build_pair_table(pulses, config)
    pair_frame.drop(columns=["pre_seq"]).to_csv(out_dir / "sample_ii_pair_table.csv.gz", index=False)

    fold_metrics, pred, scans = S16F.run_loro(pair_frame, config)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    scans.to_csv(out_dir / "threshold_scans.csv", index=False)

    agg = S16F.aggregate_from_predictions(pred)
    ci = S16F.bootstrap_ci(pred, config, rng)
    benchmark = agg.merge(ci, on=["method", "shuffled_proxy"])
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    ci.to_csv(out_dir / "bootstrap_cis.csv", index=False)

    checks = S16F.leakage_checks(pred, fold_metrics, pair_frame, config)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    actual = benchmark[~benchmark["shuffled_proxy"]].copy()
    actual["winner_score"] = actual["tail_fraction_after"] + 0.05 * np.maximum(0.0, 0.85 - actual["timing_efficiency"])
    winner_row = actual.sort_values(["winner_score", "sigma68_after_ns"]).iloc[0]
    proxy_winner = str(winner_row["method"])
    S16F.plot_outputs(out_dir, agg, ci, pred, proxy_winner)

    input_hash_rows = [
        {"file": str(S16F.raw_file(config, run)), "sha256": S16F.sha256_file(S16F.raw_file(config, run))}
        for run in S16F.configured_runs(config)
    ]
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    git = S16F.git_commit()
    baseline_tail = float(actual["tail_fraction_before"].iloc[0])
    baseline_sigma = float(actual["sigma68_before_ns"].iloc[0])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-06-10",
        "reproduced": bool(match["pass"].all()),
        "reproduction_pass": bool(match["pass"].all()),
        "raw_reproduction": match.to_dict(orient="records"),
        "direct_forced_random_truth": {
            "status": "ready" if direct_truth_ready else "blocked_missing_truth",
            **acquisition,
        },
        "split": "Sample-II leave-one-run-out by run",
        "baseline": {
            "method": "CFD20 pair residual before proxy veto",
            "tail_fraction_abs_gt5ns": baseline_tail,
            "sigma68_ns": baseline_sigma,
        },
        "traditional": actual[actual["method"] == "traditional_quantile"].drop(columns=["winner_score"]).iloc[0].to_dict(),
        "ml": actual[actual["method"] == proxy_winner].drop(columns=["winner_score"]).iloc[0].to_dict(),
        "methods": actual.drop(columns=["winner_score"]).to_dict(orient="records"),
        "winner": {
            "method": proxy_winner,
            "scope": "fallback_proxy_timing_tail_benchmark",
            "direct_truth_status": "ready" if direct_truth_ready else "blocked_missing_truth",
            "criterion": "lowest held-out post-veto proxy tail fraction with timing-efficiency penalty below 0.85",
            "tail_fraction_after": float(winner_row["tail_fraction_after"]),
            "tail_fraction_after_ci": [
                float(winner_row["tail_fraction_after_ci_low"]),
                float(winner_row["tail_fraction_after_ci_high"]),
            ],
            "timing_efficiency": float(winner_row["timing_efficiency"]),
            "timing_efficiency_ci": [
                float(winner_row["timing_efficiency_ci_low"]),
                float(winner_row["timing_efficiency_ci_high"]),
            ],
            "tail_capture": float(winner_row["tail_capture"]),
            "sigma68_after_ns": float(winner_row["sigma68_after_ns"]),
            "sigma68_delta_ns": float(winner_row["sigma68_delta_ns"]),
        },
        "ml_beats_baseline": bool(
            float(winner_row["tail_fraction_after"])
            < float(actual[actual["method"] == "traditional_quantile"]["tail_fraction_after"].iloc[0])
        ),
        "shuffled_proxy_controls": benchmark[benchmark["shuffled_proxy"]].to_dict(orient="records"),
        "falsification": {
            "preregistered_metric": "direct forced/random availability first; fallback proxy held-out post-veto tail fraction",
            "n_tries": 6,
            "leakage_checks_pass": bool(checks["pass"].all()),
        },
        "input_sha256": input_hash_rows,
        "git_commit": git,
        "critic": "pending",
        "caveat": "Direct forced/random truth is absent in the mounted ROOT/archive mirrors; proxy winner is not a physical pedestal-truth winner.",
        "next_tickets": config.get("next_tickets", []),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=False) + "\n", encoding="utf-8")

    numbers = {
        "git_commit": git,
        "match_rows": S16F.format_match_table(match),
        "benchmark_rows": S16F.format_benchmark_table(agg, ci),
        "winner": proxy_winner,
        "baseline_tail": baseline_tail,
        "baseline_sigma": baseline_sigma,
        "winner_fold_rows": S16F.format_fold_table(fold_metrics, proxy_winner),
        "leakage_rows": S16F.format_leakage_table(checks),
    }
    write_proxy_report(out_dir, config, numbers, acquisition, result)

    manifest = {
        "script": str(Path(__file__)),
        "config": str(args.config),
        "output_dir": str(out_dir),
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git,
        "python": sys.version,
        "platform": platform.platform(),
        "torch_available": bool(S16F.torch is not None),
        "commands": [f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"],
        "random_seed": int(config["models"]["random_seed"]),
        "input_sha256": input_hash_rows,
        "output_sha256": S16F.output_hashes(out_dir),
        "elapsed_seconds": float(time.time() - t0),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "proxy_winner": proxy_winner, "elapsed_seconds": time.time() - t0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
