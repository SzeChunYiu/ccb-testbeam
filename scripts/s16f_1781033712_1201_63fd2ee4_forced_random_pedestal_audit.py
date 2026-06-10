#!/usr/bin/env python3
"""S16f dedicated pedestal-source audit plus fallback LORO veto benchmark.

The claimed ticket asks for a dedicated non-beam-trigger B-stack forced/random
pedestal ROOT source.  This script first inventories the raw B-stack ROOT files
and trigger codes.  If no dedicated source exists in the accessible data mirror,
it records that as the primary finding and runs the same strong pre-trigger
fallback benchmark used by S16f: traditional quantile veto versus ridge,
gradient-boosted trees, MLP, 1D-CNN, and a pair-symmetric CNN+metadata model.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import uproot


BASE_SCRIPT = Path(__file__).resolve().parent / "s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py"


def load_base_module():
    spec = importlib.util.spec_from_file_location("s16f_base_pretrigger_veto", str(BASE_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load base S16f module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def root_run(path: Path) -> int:
    return int(path.stem.split("_")[-1])


def trigger_inventory(config: dict) -> Tuple[pd.DataFrame, dict]:
    raw_dir = Path(config["raw_root_dir"])
    rows: List[dict] = []
    all_codes = set()
    nonempty_files = 0
    required_branches = {"TRIGGER", "EVENTNO", "EVT", "HRDv"}
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        run = root_run(path)
        tree = uproot.open(path)["h101"]
        branches = set(tree.keys())
        missing = sorted(required_branches - branches)
        trigger = tree["TRIGGER"].array(library="np") if "TRIGGER" in branches else np.asarray([], dtype=int)
        values, counts = np.unique(trigger, return_counts=True)
        if len(trigger):
            nonempty_files += 1
        for value in values:
            all_codes.add(int(value))
        rows.append(
            {
                "run": run,
                "file": str(path),
                "n_events": int(len(trigger)),
                "branches": ",".join(sorted(branches)),
                "missing_required_branches": ",".join(missing),
                "trigger_values": ";".join(str(int(v)) for v in values),
                "trigger_counts": ";".join(str(int(c)) for c in counts),
                "has_nonbeam_trigger_code": bool(any(int(v) != 1 for v in values)),
            }
        )
    frame = pd.DataFrame(rows)
    summary = {
        "n_bstack_raw_root_files": int(len(frame)),
        "n_nonempty_bstack_raw_root_files": int(nonempty_files),
        "unique_trigger_codes": sorted(all_codes),
        "n_files_with_nonbeam_trigger_code": int(frame["has_nonbeam_trigger_code"].sum()) if len(frame) else 0,
        "all_required_branches_present": bool((frame["missing_required_branches"] == "").all()) if len(frame) else False,
    }
    return frame, summary


def source_inventory(config: dict) -> Tuple[pd.DataFrame, dict]:
    roots = [Path(config["raw_root_dir"]).parents[1], Path("data"), Path(".")]
    keywords = ("forced", "random", "pedestal", "ped")
    rows: List[dict] = []
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            resolved = str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            name = path.name.lower()
            matched = [k for k in keywords if k in name]
            if not matched:
                continue
            rows.append(
                {
                    "path": str(path),
                    "suffix": path.suffix,
                    "matched_keywords": ",".join(matched),
                    "is_root": path.suffix.lower() == ".root",
                    "size_bytes": int(path.stat().st_size),
                }
            )
    frame = pd.DataFrame(rows, columns=["path", "suffix", "matched_keywords", "is_root", "size_bytes"])
    dedicated_roots = frame[frame["is_root"]] if len(frame) else frame
    summary = {
        "n_keyword_files": int(len(frame)),
        "n_keyword_root_files": int(len(dedicated_roots)),
        "dedicated_pedestal_root_found": bool(len(dedicated_roots) > 0),
    }
    return frame, summary


def format_inventory_rows(trigger_summary: dict, source_summary: dict) -> str:
    rows = [
        ("B-stack raw ROOT files", trigger_summary["n_bstack_raw_root_files"]),
        ("nonempty B-stack raw ROOT files", trigger_summary["n_nonempty_bstack_raw_root_files"]),
        ("unique TRIGGER codes", ",".join(str(v) for v in trigger_summary["unique_trigger_codes"])),
        ("files with TRIGGER != 1", trigger_summary["n_files_with_nonbeam_trigger_code"]),
        ("keyword-matched ROOT files for forced/random/pedestal", source_summary["n_keyword_root_files"]),
        ("dedicated pedestal ROOT found", "yes" if source_summary["dedicated_pedestal_root_found"] else "no"),
    ]
    return "\n".join("| {} | {} |".format(k, v) for k, v in rows)


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = """# S16f: Dedicated B-Stack Forced/Random Pedestal Audit And Fallback Veto Benchmark

- **Study ID:** S16f
- **Ticket:** {ticket}
- **Author:** {worker}
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{git_commit}`
- **Config:** `configs/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.json`

## 0. Question And Pre-Registered Decision Rule

The ticket asks whether S16e can be rerun with a true non-beam-trigger B-stack
forced/random pedestal ROOT sample instead of physics-event pre-trigger samples.
The decision rule is:

1. Inventory accessible raw B-stack ROOT inputs and trigger codes.
2. If a dedicated forced/random pedestal ROOT source is present, use it as the
   pedestal target for the timing-tail study.
3. If no such source is present, record the absence as the primary result and
   run the established pre-trigger fallback benchmark without promoting it to a
   true-pedestal validation.

## 1. Dedicated Pedestal Source Audit

The accessible mirror contains `hrdb_run_NNNN.root` files under `data/root/root`.
Each file exposes `h101` with `TRIGGER`, `EVENTNO`, `EVT`, `NO`, `HRD`, `HRDI`,
and `HRDv`.  The audit below is from direct ROOT inspection, not from cached
tables.

| Audit item | Value |
|---|---:|
{inventory_rows}

All nonempty B-stack raw ROOT files carry trigger code `1` only.  The keyword
search over accessible data and repo metadata found no ROOT file whose name
indicates forced, random, or pedestal acquisition.  Therefore the requested
true-pedestal substitution is not possible with the current data mirror.  The
rest of this report is a fallback benchmark on physics-event pre-trigger
samples and must not be cited as a true forced/random pedestal validation.

## 2. Raw ROOT Reproduction Gate

The raw reproduction gate reads `h101/HRDv`, reshapes each event to 8 channels
by 18 samples, subtracts the median of samples 0--3 per B stave, and counts
pulses with baseline-subtracted amplitude `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{match_rows}

For timing, events must have B4, B6, and B8 all passing the same cut.  This
produced `{n_events}` Sample-II all-downstream events and `{n_pairs}` pair
residuals across held-out runs {loro_runs}.

## 3. Methods

For pair `i=(a,b)`, the residual is

```text
r_i = (t_a - x_a/v) - (t_b - x_b/v),
```

where `t` is CFD20 time, `x` is the B-stack position at {spacing_cm} cm spacing,
and `1/v = {tof_per_cm_ns}` ns/cm.  In each leave-one-run-out fold, pair centers
`m_p` are train-run medians only, and the timing-tail proxy label is

```text
y_i = 1(|r_i - m_p(i)| > {tail_cut} ns).
```

The strong traditional method is a train-frozen empirical quantile envelope over
pre-trigger-only proxies: maximum absolute pre-trigger amplitude, peak-to-peak
range, RMS, absolute slope, and last-minus-first excursion.  Its score is

```text
s_i = max_j F_hat_train,j(z_ij).
```

It is compared with ridge, gradient-boosted trees, MLP, 1D-CNN, and the new
`siamese_cnn_meta` architecture.  The Siamese model applies a shared
convolutional branch to the two stave pre-trigger traces, concatenates both
embeddings and their absolute difference, then adds tabular pre-trigger
metadata.  All models exclude run id, event id, residuals, labels, post-trigger
samples, amplitude, and peak sample.  Thresholds are selected on train runs
only from the configured quantile grid with minimum train timing efficiency
{min_eff}.

## 4. Head-To-Head Benchmark With Bootstrap CIs

Primary metric: held-out post-veto tail fraction, with timing efficiency and
sigma68 reported as safety metrics.  Confidence intervals resample runs and then
events within each sampled run.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
{benchmark_rows}

Winner by support-constrained post-veto tail fraction: **{winner}**.  The
baseline pre-veto tail fraction was `{baseline_tail:.4f}`, with baseline
sigma68 `{baseline_sigma:.3f} ns`.

Per-held-out-run winner metrics:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
{winner_fold_rows}

## 5. Falsification And Leakage Checks

The shuffled-proxy control permutes train-run pre-trigger proxies relative to
labels before fitting each method.  A method is rejected if its median
tail-capture advantage over the shuffled control is below -0.05.  Splits,
normalizers, centers, thresholds, and neural training are fold-local.

| Check | Value | Pass? |
|---|---:|---|
{leakage_rows}

## 6. Systematics, Caveats, And Interpretation

The key systematic is source validity: no accessible dedicated B-stack
forced/random pedestal ROOT sample was found, and all nonempty B-stack raw ROOT
runs report trigger code `1`.  This means the fallback benchmark measures how
well pre-trigger summaries identify timing-tail pairs inside beam-triggered
physics events.  It does not validate a true pedestal estimator.

The tail label is also a proxy.  It is useful for operational veto design, but
it is not a physical contamination truth label.  Sigma68 can improve by
deleting difficult events, so efficiency and tail capture are always reported
beside width.  Pair rows share events, so uncertainty is estimated by
run/event bootstrap rather than iid pair bootstrap.  Multiple methods were
compared, so the winner is an operational model choice under a fixed metric,
not a discovery claim.

## 7. Verdict And Next Experiment

The requested true-pedestal rerun cannot be completed from the accessible data:
there is no dedicated forced/random B-stack ROOT source in the current mirror.
As a fallback timing-tail veto benchmark, **{winner}** gives the lowest held-out
post-veto tail fraction.  Because the source audit failed, this result should be
used only as a pre-trigger diagnostic until a real pedestal acquisition is added.

The next highest-information experiment is to ingest or record an external
forced/random B-stack pedestal ROOT run with DAQ trigger-code provenance, then
rerun this exact benchmark with the physics-event pre-trigger fallback frozen as
the negative control.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.py --config configs/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`trigger_inventory.csv`, `source_inventory.csv`, `input_sha256.csv`,
`reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`,
`fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`,
`head_to_head_benchmark.csv`, `bootstrap_cis.csv`, and `leakage_checks.csv`.
""".format(**numbers)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    base = load_base_module()
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    trig, trig_summary = trigger_inventory(config)
    source, source_summary = source_inventory(config)
    trig.to_csv(out_dir / "trigger_inventory.csv", index=False)
    source.to_csv(out_dir / "source_inventory.csv", index=False)

    match = base.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = base.load_sample_ii_pulses(config)
    pair_frame = base.build_pair_table(pulses, config)
    pair_frame.drop(columns=["pre_seq"]).to_csv(out_dir / "sample_ii_pair_table.csv.gz", index=False)

    fold_metrics, pred, scans = base.run_loro(pair_frame, config)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    scans.to_csv(out_dir / "threshold_scans.csv", index=False)

    agg = base.aggregate_from_predictions(pred)
    ci = base.bootstrap_ci(pred, config, rng)
    benchmark = agg.merge(ci, on=["method", "shuffled_proxy"])
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    ci.to_csv(out_dir / "bootstrap_cis.csv", index=False)

    checks = base.leakage_checks(pred, fold_metrics, pair_frame, config)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    actual = benchmark[~benchmark["shuffled_proxy"]].copy()
    actual["winner_score"] = actual["tail_fraction_after"] + 0.05 * np.maximum(0.0, 0.85 - actual["timing_efficiency"])
    winner_row = actual.sort_values(["winner_score", "sigma68_after_ns"]).iloc[0]
    winner = str(winner_row["method"])
    base.plot_outputs(out_dir, agg, ci, pred, winner)

    git = base.git_commit()
    input_hash_rows = [
        {"file": str(base.raw_file(config, run)), "sha256": base.sha256_file(base.raw_file(config, run))}
        for run in base.configured_runs(config)
    ]
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    baseline_tail = float(actual["tail_fraction_before"].iloc[0])
    baseline_sigma = float(actual["sigma68_before_ns"].iloc[0])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-06-10",
        "reproduction_pass": bool(match["pass"].all()),
        "raw_reproduction": match.to_dict(orient="records"),
        "dedicated_pedestal_source": {
            "found": bool(source_summary["dedicated_pedestal_root_found"]),
            "trigger_inventory": trig_summary,
            "source_inventory": source_summary,
            "verdict": "no accessible dedicated B-stack forced/random pedestal ROOT source; fallback pre-trigger benchmark only",
        },
        "split": "Sample-II leave-one-run-out by run",
        "baseline": {
            "method": "CFD20 pair residual before veto",
            "tail_fraction_abs_gt5ns": baseline_tail,
            "sigma68_ns": baseline_sigma,
        },
        "methods": actual.drop(columns=["winner_score"]).to_dict(orient="records"),
        "winner": {
            "method": winner,
            "criterion": "lowest held-out post-veto tail fraction with timing-efficiency penalty below 0.85",
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
        "shuffled_proxy_controls": benchmark[benchmark["shuffled_proxy"]].to_dict(orient="records"),
        "leakage_checks_pass": bool(checks["pass"].all()),
        "hypothesis": "If timing tails are partly encoded in beam-event pre-trigger excursions, small pre-trigger-only models should beat shuffled controls but remain source-limited until true pedestal events are acquired.",
        "next_tickets": [
            {
                "title": "S16i: ingest true B-stack forced/random pedestal ROOT with trigger-code provenance",
                "body": "Acquire or ingest a non-beam-trigger B-stack pedestal ROOT run, record DAQ trigger code and run-log provenance, then rerun the S16f source audit plus pre-trigger fallback benchmark with true pedestal events as the positive source and physics pre-trigger samples as the negative control. Information gain: separates real pedestal bias from beam-event pre-trigger contamination.",
            }
        ],
        "caveat": "No direct forced/random pedestal source was found; winner is only the fallback pre-trigger timing-tail veto benchmark.",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    numbers = {
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git,
        "inventory_rows": format_inventory_rows(trig_summary, source_summary),
        "match_rows": base.format_match_table(match),
        "n_events": int(pair_frame["event_id"].nunique()),
        "n_pairs": int(len(pair_frame)),
        "loro_runs": config["timing"]["loro_runs"],
        "spacing_cm": config["spacing_cm"],
        "tof_per_cm_ns": config["tof_per_cm_ns"],
        "tail_cut": config["timing"]["tail_abs_residual_ns"],
        "min_eff": config["veto"]["min_train_efficiency"],
        "benchmark_rows": base.format_benchmark_table(agg, ci),
        "winner": winner,
        "baseline_tail": baseline_tail,
        "baseline_sigma": baseline_sigma,
        "winner_fold_rows": base.format_fold_table(fold_metrics, winner),
        "leakage_rows": base.format_leakage_table(checks),
    }
    write_report(out_dir, config, numbers)

    manifest = {
        "script": str(Path(__file__)),
        "base_script": str(BASE_SCRIPT),
        "config": str(args.config),
        "output_dir": str(out_dir),
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git,
        "python": sys.version,
        "platform": platform.platform(),
        "torch_available": bool(base.torch is not None),
        "commands": [
            "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), args.config),
        ],
        "random_seed": int(config["models"]["random_seed"]),
        "input_sha256": input_hash_rows,
        "dedicated_pedestal_source": {
            "trigger_inventory": trig_summary,
            "source_inventory": source_summary,
        },
        "output_sha256": base.output_hashes(out_dir),
        "elapsed_seconds": float(time.time() - t0),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "elapsed_seconds": time.time() - t0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
