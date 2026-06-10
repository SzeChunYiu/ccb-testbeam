#!/usr/bin/env python3
"""S10f amplitude-binned/asymmetric templates on the S10d delay metric."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S10D = load_module("s10d_two_pulse_resolvability_livetime", Path("scripts/s10d_two_pulse_resolvability_livetime.py"))
S11C = load_module("s11c_amp_binned_asymmetric_templates", Path("scripts/s11c_amp_binned_asymmetric_templates.py"))


TRAD_LABEL = "amp_binned_asymmetric_template_fit"
ML_LABEL = "compact_mlp_classifier_regressor"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def fmt_delay(value) -> str:
    value = float(value)
    return f"{value:.1f}" if np.isfinite(value) else "not stable"


def fmt_ci(low, high) -> str:
    low = float(low)
    high = float(high)
    if np.isfinite(low) and np.isfinite(high):
        return f"[{low:.1f}, {high:.1f}]"
    return "not stable"


def resolvability_by_delay(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    criteria = config["resolvability_criteria"]
    max_t = float(criteria["max_abs_timing_bias_ns"])
    max_area = float(criteria["max_abs_area_bias_fraction"])
    held = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    rows = []
    for sep, group in held.groupby("true_sep_sample"):
        for prefix, label in [("trad", TRAD_LABEL), ("ml", ML_LABEL)]:
            got = S10D.bias_metrics(group, prefix)
            rows.append(
                {
                    "delay_sample": float(sep),
                    "delay_ns": float(sep) * float(config["sample_period_ns"]),
                    "method": label,
                    **got,
                    "passes_bias_criteria": bool(got["abs_timing_bias_ns"] < max_t and got["abs_area_bias_fraction"] < max_area),
                    "timing_bias_requirement_ns": max_t,
                    "area_bias_requirement_fraction": max_area,
                }
            )
    return pd.DataFrame(rows).sort_values(["method", "delay_sample"]).reset_index(drop=True)


def first_stable_delay(rows: pd.DataFrame) -> float:
    rows = rows.sort_values("delay_sample").reset_index(drop=True)
    if rows.empty:
        return float("nan")
    passes = rows["passes_bias_criteria"].to_numpy(dtype=bool)
    delays = rows["delay_ns"].to_numpy(dtype=float)
    for idx in range(len(rows)):
        if bool(np.all(passes[idx:])):
            return float(delays[idx])
    return float("nan")


def delay_summary(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    delay_rows = resolvability_by_delay(frame, config)
    summary_rows = []
    boot_rows = []
    run_rows = []
    n_boot = int(config["resolvability_criteria"]["bootstrap_samples"])
    held = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    held_runs = sorted(int(x) for x in held["source_run"].unique())
    for label in [TRAD_LABEL, ML_LABEL]:
        method_rows = delay_rows[delay_rows["method"] == label]
        delay_ns = first_stable_delay(method_rows)
        summary_rows.append({"method": label, "resolvable_delay_ns": delay_ns, "n_heldout_runs": len(held_runs)})

        vals = []
        for _ in range(n_boot):
            pieces = []
            for run in rng.choice(held_runs, size=len(held_runs), replace=True):
                sub = held[held["source_run"] == int(run)]
                if len(sub):
                    pieces.append(sub.iloc[rng.choice(np.arange(len(sub)), size=len(sub), replace=True)])
            if not pieces:
                continue
            boot_frame = pd.concat(pieces, ignore_index=True)
            vals.append(first_stable_delay(resolvability_by_delay(boot_frame, config)[lambda x: x["method"] == label]))
        finite = np.asarray([value for value in vals if np.isfinite(value)], dtype=float)
        boot_rows.append(
            {
                "method": label,
                "metric": "resolvable_delay_ns",
                "value": delay_ns,
                "ci_low": float(np.percentile(finite, 2.5)) if len(finite) else float("nan"),
                "ci_high": float(np.percentile(finite, 97.5)) if len(finite) else float("nan"),
                "n_bootstrap": int(len(vals)),
                "n_finite": int(len(finite)),
            }
        )

        for run, group in held.groupby("source_run"):
            by_delay = resolvability_by_delay(group, config)
            run_rows.append(
                {
                    "source_run": int(run),
                    "method": label,
                    "resolvable_delay_ns": first_stable_delay(by_delay[by_delay["method"] == label]),
                    "n_positive": int(len(group)),
                }
            )
    return delay_rows, pd.DataFrame(summary_rows), pd.DataFrame(boot_rows), pd.DataFrame(run_rows)


def save_plots(out_dir: Path, overall: pd.DataFrame, by_sep: pd.DataFrame, by_ratio: pd.DataFrame, delay_rows: pd.DataFrame) -> None:
    S11C.save_plots(out_dir, overall, by_sep, by_ratio)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for method, sub in delay_rows.groupby("method"):
        sub = sub.sort_values("delay_ns")
        ax.plot(sub["delay_ns"], sub["abs_timing_bias_ns"], "o-", label=f"{method} time")
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.set_xlabel("true two-pulse delay (ns)")
    ax.set_ylabel("absolute median constituent timing bias (ns)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_resolvability_delay_bias.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    s10: pd.DataFrame,
    s10b: pd.DataFrame,
    templates: pd.DataFrame,
    overall: pd.DataFrame,
    delay_ci: pd.DataFrame,
    run_delay: pd.DataFrame,
    leak: pd.DataFrame,
    runtime: float,
) -> None:
    trad = overall[overall["method"] == TRAD_LABEL].iloc[0]
    ml = overall[overall["method"] == ML_LABEL].iloc[0]
    trad_delay = delay_ci[delay_ci["method"] == TRAD_LABEL].iloc[0]
    ml_delay = delay_ci[delay_ci["method"] == ML_LABEL].iloc[0]
    s10d_anchor = float(config["s10d_anchor"]["expected_traditional_delay_ns"])
    reduced = np.isfinite(float(trad_delay["value"])) and float(trad_delay["value"]) < 60.0
    verdict = (
        "The amplitude-binned/asymmetric fit reduces the S10d constrained-fit delay below 60 ns in this held-out closure."
        if reduced
        else "The amplitude-binned/asymmetric fit does not reduce the S10d constrained-fit delay below 60 ns in this held-out closure."
    )
    run_lines = [
        f"| {int(row.source_run)} | {row.method} | {fmt_delay(row.resolvable_delay_ns)} | {int(row.n_positive)} |"
        for row in run_delay.itertuples()
    ]
    leak_flags = int((~leak["pass"].astype(bool)).sum())
    template_fallbacks = int(templates["fallback_used"].sum()) if "fallback_used" in templates else 0
    text = f"""# Study report: S10f - amplitude-binned two-pulse templates

- **Study ID:** S10f
- **Ticket:** `{config['ticket_id']}`
- **Author:** `{config['worker']}`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s10f_1781013481_902_5d6a5b89.json`

## 0. Question

Do amplitude-binned and asymmetric raw-pulse templates reduce the S10d constrained-fit resolvability delay below 60 ns? The metric is the first held-out delay where `abs(median timing bias) < 1 ns` and `abs(median total-area bias) < 0.20`, using run-held-out bootstrap intervals.

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first and passed: `{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus `{int(match.iloc[0]['report_value'])}` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was rerun from raw ROOT before this benchmark. Reproduced AP values are `{s10['reproduced'].round(4).tolist()}` for `{s10['quantity'].tolist()}` with the documented 0.006 absolute tolerance.

The S10b live-time gate was then rerun from raw ROOT. It reproduced `{float(s10b[s10b['quantity'] == 'S10b measured traditional live10 ns'].iloc[0]['reproduced']):.2f} ns` for measured live10 and `{float(s10b[s10b['quantity'] == 'S10b measured-tau rescaled Rmax MHz'].iloc[0]['reproduced']):.2f} MHz` for the measured-tau rescaled combined Rmax.

## 2. Methods

Training source runs are `{config['benchmark_runs']['train']}` and held-out source runs are `{config['benchmark_runs']['heldout']}`. The injected benchmark uses S01-style empirical templates and real residuals derived from raw ROOT pulses; template construction excludes held-out runs.

The traditional method builds train-run-only template candidates by stave, amplitude quantile bin, and late-tail shape class. The two-pulse fit may use different primary and secondary candidates, scans first-pulse timing offsets and fixed separation hypotheses, and solves amplitudes plus baseline by least squares under configured ratio and baseline bounds. It wrote {len(templates)} candidates; {template_fallbacks} low-stat bins used a broader fallback.

The ML method is a compact MLP classifier plus MLP regressor trained on the same amplitude-binned overlay benchmark. It sees waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Resolvability result

S10d's constrained-fit anchor delay was {s10d_anchor:.1f} ns. {verdict}

| Method | delay ns | bootstrap 95% CI ns | AP | time RMS ns | area bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| amp-binned asymmetric template fit | {fmt_delay(trad_delay['value'])} | {fmt_ci(trad_delay['ci_low'], trad_delay['ci_high'])} | {trad['detection_ap']:.3f} | {trad['time_rms_ns']:.2f} | {trad['charge_fractional_bias']:.3f} | {trad['failure_rate']:.3f} |
| compact ML | {fmt_delay(ml_delay['value'])} | {fmt_ci(ml_delay['ci_low'], ml_delay['ci_high'])} | {ml['detection_ap']:.3f} | {ml['time_rms_ns']:.2f} | {ml['charge_fractional_bias']:.3f} | {ml['failure_rate']:.3f} |

Detailed delay rows are in `resolvability_by_delay.csv`; run-held-out bootstrap intervals are in `resolvability_bootstrap_ci.csv`.

## 4. Held-out runs

| Run | Method | delay ns | positives |
|---:|---|---:|---:|
{chr(10).join(run_lines)}

## 5. Leakage checks

Run splitting is strict, event ids do not overlap, and template source runs exclude held-out runs. A shuffled-label classifier gives held-out AP `{float(leak[leak['check'] == 'shuffled_train_labels_heldout_ap'].iloc[0]['value']):.3f}`. Too-good sentinels for time RMS < 5 ns or AP > 0.98 recorded {leak_flags} flags in `leakage_checks.csv`.

## 6. Threats to validity

This is a data-driven closure on synthetic overlaps from raw-pulse templates and residuals, not a direct measurement of real beam pile-up. It is appropriate for testing whether the richer fit improves the S10d template-like closure metric; it does not prove performance on all high-current pathologies.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s10f_1781013481_902_5d6a5b89_amp_binned_resolvability.py --config configs/s10f_1781013481_902_5d6a5b89.json
```

Runtime in this run was `{runtime:.2f}` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, delay tables, held-out metrics, leakage checks, and figures.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s10f_1781013481_902_5d6a5b89.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = S10D.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT S00 reproduction failed")

    s10 = S10D.reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 injection AP reproduction failed")

    s10b, s10b_heldout, s10b_rmax = S10D.reproduce_s10b_live_time(config)
    s10b.to_csv(out_dir / "s10b_reproduction.csv", index=False)
    s10b_heldout.to_csv(out_dir / "s10b_heldout_live_time.csv", index=False)
    s10b_rmax.to_csv(out_dir / "s10b_poisson_rmax_table.csv", index=False)
    if not bool(s10b["pass"].all()):
        raise RuntimeError("raw ROOT S10b live-time reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = S11C.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    template_clean = clean[clean["run"].isin(train_runs)]
    base_templates, base_template_summary = S11C.build_templates(template_clean, config)
    base_template_summary.to_csv(out_dir / "s01_template_summary.csv", index=False)

    train_events, train_wave = S11C.generate_benchmark(clean, base_templates, config, "train", train_runs, rng)
    held_events, held_wave = S11C.generate_benchmark(clean, base_templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])

    rich_templates, template_summary = S11C.build_amp_binned_templates(template_clean, config)
    template_summary.to_csv(out_dir / "s10f_template_summary.csv", index=False)
    trad = S11C.run_amp_binned_template_fits(held_events, held_wave, rich_templates, config)
    ml, ml_cv = S11C.run_ml(events, waveforms, config)
    ml_cv.to_csv(out_dir / "ml_group_cv.csv", index=False)

    combined = held_events.merge(trad, on="event_id").merge(ml, on="event_id")
    combined.to_csv(out_dir / "injected_events_with_predictions.csv", index=False)
    overall = S11C.summarize_methods(combined, rng, config)
    overall.to_csv(out_dir / "head_to_head_overall.csv", index=False)
    heldout_by_run = S11C.summarize_heldout_by_run(combined)
    heldout_by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    by_sep = S11C.summarize_bins(combined, "true_sep_sample")
    by_ratio = S11C.summarize_bins(combined, "true_ratio")
    by_sep.to_csv(out_dir / "metrics_by_separation.csv", index=False)
    by_ratio.to_csv(out_dir / "metrics_by_ratio.csv", index=False)
    delay_rows, delay_overall, delay_ci, run_delay = delay_summary(combined, config, rng)
    delay_rows.to_csv(out_dir / "resolvability_by_delay.csv", index=False)
    delay_overall.to_csv(out_dir / "resolvability_summary.csv", index=False)
    delay_ci.to_csv(out_dir / "resolvability_bootstrap_ci.csv", index=False)
    run_delay.to_csv(out_dir / "run_heldout_resolvability.csv", index=False)
    leak = S11C.leakage_checks(events, waveforms, ml, config, combined)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    save_plots(out_dir, overall, by_sep, by_ratio, delay_rows)

    all_runs = sorted(set(S10D.configured_runs(config) + train_runs + heldout_runs + list(range(44, 58))))
    input_paths = [raw_file(config, run) for run in all_runs]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, match, s10, s10b, template_summary, overall, delay_ci, run_delay, leak, runtime)

    trad_row = overall[overall["method"] == TRAD_LABEL].iloc[0]
    ml_row = overall[overall["method"] == ML_LABEL].iloc[0]
    trad_delay = delay_ci[delay_ci["method"] == TRAD_LABEL].iloc[0]
    ml_delay = delay_ci[delay_ci["method"] == ML_LABEL].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all() and (len(s10) == 0 or s10["pass"].all()) and s10b["pass"].all()),
        "s10d_anchor": {
            "traditional_delay_ns": float(config["s10d_anchor"]["expected_traditional_delay_ns"]),
            "ml_delay_ns": float(config["s10d_anchor"]["expected_ml_delay_ns"]),
        },
        "traditional": {
            "method": "amplitude_binned_asymmetric_s01_template_fit",
            "metric": "heldout_resolvable_delay_ns_for_abs_timing_bias_lt_1ns_and_abs_area_bias_lt_20pct",
            "value": float(trad_delay["value"]),
            "ci": [float(trad_delay["ci_low"]), float(trad_delay["ci_high"])],
            "heldout_constituent_time_rms_ns": float(trad_row["time_rms_ns"]),
            "detection_ap": float(trad_row["detection_ap"]),
            "charge_fractional_bias": float(trad_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(trad_row["charge_fractional_res68"]),
            "failure_rate": float(trad_row["failure_rate"]),
        },
        "ml": {
            "method": "compact_mlp_classifier_regressor",
            "metric": "heldout_resolvable_delay_ns_for_abs_timing_bias_lt_1ns_and_abs_area_bias_lt_20pct",
            "value": float(ml_delay["value"]),
            "ci": [float(ml_delay["ci_low"]), float(ml_delay["ci_high"])],
            "heldout_constituent_time_rms_ns": float(ml_row["time_rms_ns"]),
            "detection_ap": float(ml_row["detection_ap"]),
            "charge_fractional_bias": float(ml_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(ml_row["charge_fractional_res68"]),
            "failure_rate": float(ml_row["failure_rate"]),
        },
        "traditional_reduces_below_60_ns": bool(np.isfinite(float(trad_delay["value"])) and float(trad_delay["value"]) < 60.0),
        "ml_beats_traditional_delay": bool(float(ml_delay["value"]) < float(trad_delay["value"])),
        "falsification": {
            "split": "by source run",
            "train_runs": train_runs,
            "heldout_runs": heldout_runs,
            "leakage_checks_pass": bool(leak["pass"].all()),
            "leakage_flags": int((~leak["pass"].astype(bool)).sum()),
            "bootstrap_unit": "heldout source run",
            "n_template_candidates": int(len(template_summary)),
        },
        "s10b_reproduction": s10b.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S10g: validate S10f amplitude-binned/asymmetric fit on real high-current windows with low-current residual controls",
            "S10h: stress-test S10f with run-family residual pools and stricter synthetic-overlay realism checks",
        ],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduced": result["reproduced"],
                "traditional_delay_ns": result["traditional"]["value"],
                "ml_delay_ns": result["ml"]["value"],
                "traditional_reduces_below_60_ns": result["traditional_reduces_below_60_ns"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
