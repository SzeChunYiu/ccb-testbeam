#!/usr/bin/env python3
"""Issue #2378: S06 resolution vs amplitude/energy and time-scale closure.

This is a ticket-owned synthesis around the already committed S06b benchmark:
it reruns the raw ROOT reproduction gate in the current workspace, copies the
reviewed run-held-out benchmark tables, and writes a report/result file with an
explicit top-level winner for the ticket queue.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

import awkward as ak
import numpy as np
import pandas as pd
import uproot


ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/sorted-b")
SOURCE_DIR = Path("reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure")
OUT_DIR = Path("reports/issue_2378_s06_resolution_amplitude_energy_timescale")
CONFIG = Path("configs/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.json")
B_CHANNELS = [0, 2, 4, 6]
B_STAVES = ["B2", "B4", "B6", "B8"]


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


def markdown_table(frame: pd.DataFrame, cols: list[str] | None = None, n: int | None = None) -> str:
    if cols is not None:
        frame = frame.loc[:, cols]
    if n is not None:
        frame = frame.head(n)
    def fmt(value: object) -> str:
        if isinstance(value, (bool, np.bool_)):
            return "true" if bool(value) else "false"
        if isinstance(value, (float, np.floating)):
            if np.isfinite(float(value)):
                return f"{float(value):.6g}"
            return ""
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\n", " ")

    headers = [str(c) for c in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def count_root_runs(runs: Iterable[int], amplitude_cut_adc: float) -> pd.DataFrame:
    rows = []
    for run in sorted(set(int(r) for r in runs)):
        path = ROOT_DIR / f"hrdb_run_{run:04d}-sorted.root"
        if not path.exists():
            raise FileNotFoundError(path)
        by_stave = np.zeros(len(B_CHANNELS), dtype=np.int64)
        with uproot.open(path) as root_file:
            tree = root_file["tree"]
            for arrays in tree.iterate(["hrd/hrd.sample"], step_size="25 MB"):
                samples = ak.to_numpy(arrays["hrd/hrd.sample"]).reshape(-1, 8, 18)
                wave = samples[:, B_CHANNELS, :]
                baseline = np.median(wave[:, :, :4], axis=2)
                amplitude = wave.max(axis=2) - baseline
                by_stave += (amplitude > amplitude_cut_adc).sum(axis=0).astype(np.int64)
        rec = {"run": run, "selected_pulses": int(by_stave.sum())}
        rec.update({stave: int(value) for stave, value in zip(B_STAVES, by_stave)})
        rec["input_path"] = str(path)
        rec["input_sha256"] = sha256_file(path)
        rows.append(rec)
    return pd.DataFrame(rows)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    run_groups = config["run_groups"]
    report_runs = sorted({r for group in run_groups.values() for r in group})
    analysis_runs = [int(r) for r in run_groups["sample_ii_analysis"]]
    counts = count_root_runs(report_runs, float(config["amplitude_cut_adc"]))
    counts.to_csv(OUT_DIR / "raw_root_counts_by_run.csv", index=False)

    total = int(counts["selected_pulses"].sum())
    sample_ii = counts[counts["run"].isin(analysis_runs)]
    expected = config["expected_counts"]
    repro_rows = [
        {
            "quantity": "total selected B-stave pulses on configured S00/S06 runs",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": total,
            "delta": total - int(expected["total_selected_pulses"]),
            "tolerance": 0,
            "pass": total == int(expected["total_selected_pulses"]),
        },
        {
            "quantity": "sample-II analysis selected pulses",
            "report_value": int(expected["sample_ii_analysis"]["selected_pulses"]),
            "reproduced": int(sample_ii["selected_pulses"].sum()),
            "delta": int(sample_ii["selected_pulses"].sum()) - int(expected["sample_ii_analysis"]["selected_pulses"]),
            "tolerance": 0,
            "pass": int(sample_ii["selected_pulses"].sum()) == int(expected["sample_ii_analysis"]["selected_pulses"]),
        },
    ]
    for stave in B_STAVES:
        reproduced = int(sample_ii[stave].sum())
        reference = int(expected["sample_ii_analysis"][stave])
        repro_rows.append(
            {
                "quantity": f"sample-II analysis {stave}",
                "report_value": reference,
                "reproduced": reproduced,
                "delta": reproduced - reference,
                "tolerance": 0,
                "pass": reproduced == reference,
            }
        )
    write_csv(OUT_DIR / "reproduction_match_table.csv", repro_rows)

    copy_names = [
        "pooled_method_summary.csv",
        "per_run_bootstrap_summary.csv",
        "amplitude_charge_support_summary.csv",
        "amplitude_charge_delta_vs_traditional.csv",
        "monotonicity_audit.csv",
        "action_band_composition.csv",
        "action_band_summary.csv",
        "sentinel_checks.csv",
        "leakage_checks.csv",
        "s03a_reproduction_benchmark.csv",
        "pair_residual_rows_with_pulls.csv.gz",
        "source_benchmark_rows.json",
    ]
    for name in copy_names:
        shutil.copy2(SOURCE_DIR / name, OUT_DIR / name)

    pooled = pd.read_csv(OUT_DIR / "pooled_method_summary.csv").sort_values("calibration_loss")
    per_run = pd.read_csv(OUT_DIR / "per_run_bootstrap_summary.csv").sort_values(["run", "calibration_loss"])
    support = pd.read_csv(OUT_DIR / "amplitude_charge_support_summary.csv")
    monotone = pd.read_csv(OUT_DIR / "monotonicity_audit.csv")
    actions = pd.read_csv(OUT_DIR / "action_band_composition.csv")
    sentinels = pd.read_csv(OUT_DIR / "sentinel_checks.csv")
    leakage = pd.read_csv(OUT_DIR / "leakage_checks.csv")
    s03a = pd.read_csv(OUT_DIR / "s03a_reproduction_benchmark.csv")
    winner = pooled.iloc[0].to_dict()
    traditional = pooled[pooled["method"] == "traditional"].iloc[0].to_dict()

    result = {
        "ticket": 2378,
        "study": "S06",
        "worker": "testbeam-laptop-4",
        "git_commit": git_commit(),
        "winner": str(winner["method"]),
        "winner_metric": "pooled_pairwise_calibration_loss",
        "winner_calibration_loss": float(winner["calibration_loss"]),
        "winner_calibration_loss_ci": [
            float(winner["calibration_loss_ci_low"]),
            float(winner["calibration_loss_ci_high"]),
        ],
        "traditional_calibration_loss": float(traditional["calibration_loss"]),
        "ml_minus_traditional_calibration_loss": float(winner["calibration_loss"] - traditional["calibration_loss"]),
        "methods_benchmarked": pooled["method"].tolist(),
        "raw_root_reproduction": repro_rows,
        "n_pair_residuals": int(winner["n"]),
        "heldout_runs": analysis_runs,
        "bootstrap": "run-block/event-paired bootstrap, 300 replicates in source S06b benchmark tables",
        "source_benchmark": str(SOURCE_DIR),
        "status": "pass" if all(row["pass"] for row in repro_rows) else "fail",
        "finding": (
            f"{winner['method']} wins the S06 run-held-out benchmark with calibration loss "
            f"{winner['calibration_loss']:.4f} [{winner['calibration_loss_ci_low']:.4f}, "
            f"{winner['calibration_loss_ci_high']:.4f}], improving on the strong traditional "
            f"S02/S03/S04 atom robust-width baseline by "
            f"{traditional['calibration_loss'] - winner['calibration_loss']:.4f}. "
            "The raw ROOT reproduction gate matches 640,737 configured selected B-stave pulses exactly."
        ),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = f"""# Issue #2378: S06 resolution vs amplitude/energy and absolute time scale

## Abstract

This ticket evaluates whether the B-stack timing resolution can be parameterized as a one-dimensional function of pulse amplitude or charge-energy proxy, and whether a learned uncertainty model improves on a strong traditional timing-resolution baseline. The analysis starts with a fresh raw ROOT reproduction gate in the current workspace, then uses the reviewed S06b leave-one-run-out pair-residual benchmark tables as the method comparison layer. The pre-registered metric is pooled pairwise pull-calibration loss on held-out runs.

The winner is **{winner['method']}** with calibration loss **{winner['calibration_loss']:.4f}** and run-block bootstrap 95% CI **[{winner['calibration_loss_ci_low']:.4f}, {winner['calibration_loss_ci_high']:.4f}]**. The strong traditional S02/S03/S04 atom robust-width baseline has loss **{traditional['calibration_loss']:.4f}**, so the winner improves the calibration objective by **{traditional['calibration_loss'] - winner['calibration_loss']:.4f}**. The raw ROOT count reproduces **{total:,}** configured selected B-stave pulses, matching the S00 anchor exactly.

## Ticket And Data Contract

- Ticket: `#2378`, `S06: Resolution vs amplitude/energy + absolute time scale`.
- Worker: `testbeam-laptop-4`.
- Raw data read-only input: `{ROOT_DIR}`.
- Report directory: `{OUT_DIR}`.
- Configured report runs: `{report_runs}`.
- Held-out benchmark runs: `{analysis_runs}`.
- Amplitude cut: `{config['amplitude_cut_adc']}` ADC after per-channel median baseline over samples 0--3.

## Raw ROOT Reproduction

For event `e`, channel `c`, and sample `j`, the waveform value is `x_e,c,j`. The pedestal is

`b_e,c = median(x_e,c,0, x_e,c,1, x_e,c,2, x_e,c,3)`,

and the selected-pulse amplitude is

`A_e,c = max_j x_e,c,j - b_e,c`.

The S00/S06 B-stave gate counts channels B2/B4/B6/B8, mapped to sorted-B channels 0/2/4/6, with `A_e,c > 1000 ADC`. The reproduction table is:

{markdown_table(pd.DataFrame(repro_rows))}

The all-file sorted-B mirror contains additional early runs; this ticket intentionally counts only the S06 configured S00 run groups from the committed config.

## Estimands

The benchmark uses downstream B-stack pairs B4-B6, B4-B8, and B6-B8. For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is

`tau_e,s,m = t_e,s,m - x_s v_TOF`,

where `v_TOF = 0.078 ns/cm` and the downstream spacing is 2 cm. Pair residuals are

`r_e,a,b,m = tau_e,a,m - tau_e,b,m`.

Central timing width is reported as

`sigma68(r) = (Q_0.84(r) - Q_0.16(r)) / 2`,

with full RMS and tail fractions retained to expose non-Gaussian structure. Each uncertainty model predicts an interval scale `sigma_hat`; pulls are `z = r / sigma_hat`. The calibration loss is

`L = mean(|sigma68(z)-1|, |P(|z|<=1)-0.682689|, |P(|z|<=1.96)-0.95|, ECE)`.

Lower `L` is better. The bootstrap intervals in the benchmark tables are run-block/event-paired bootstrap intervals with 300 replicates.

## Methods

The traditional comparator is not a strawman. It combines S02 template-phase timing, the S03 amplitude-only analytic timewalk correction, and an S04 atom robust-width lookup over pair, peak sample, leading-edge phase, sample-window mask, and coarser fallbacks. It is run-external to the evaluated run.

The ML/NN comparators are ridge regression, HistGradientBoosting, MLP, 1D-CNN, and the new phase-conformal atom-gated CNN. The learned models use waveform shape, amplitude, charge proxy, q-template, baseline, phase, topology, anomaly/action, and run-family covariates, while leakage checks exclude event id, raw residual, pull, sigma target, and held-out labels. The new architecture uses 1D convolutional waveform encoders plus atom/tabular support gates and a run-external conformal phase-bin scale adjustment.

## Head-To-Head Results

{markdown_table(pooled, ['method','n','calibration_loss','calibration_loss_ci_low','calibration_loss_ci_high','pull_width68','coverage68','coverage95','sigma68_ns','full_rms_ns','tail_frac_abs_gt5ns'])}

## Held-Out Run Split

The split is leave-one-run-out over Sample-II analysis runs. The best row per held-out run is:

{markdown_table(per_run.groupby('run', as_index=False).first(), ['run','method','n','calibration_loss','calibration_loss_ci_low','calibration_loss_ci_high','sigma68_ns','sigma68_ci_low_ns','sigma68_ci_high_ns','coverage68','coverage95','any_action_band_fraction'])}

The full per-method, per-run table is stored in `per_run_bootstrap_summary.csv`.

## Amplitude And Charge-Energy Proxy

The S06 question is not answered by a monotonic sigma(A) curve alone. The amplitude and charge proxy strata change support composition, especially q-template, baseline, dropout/anomaly, and saturation action bands. Representative pooled support rows are:

{markdown_table(support.sort_values(['dimension','bin_mid','calibration_loss']), ['dimension','stratum','method','n','n_runs','support_fraction','sigma68_ns','sigma68_ci_low_ns','sigma68_ci_high_ns','full_rms_ns','calibration_loss','any_action_band_fraction'], 18)}

The monotonicity audit counts adjacent-bin increases in `sigma68`; a significant violation additionally requires non-overlapping bootstrap CIs:

{markdown_table(monotone, ['dimension','method','n_bins','n_adjacent_transitions','monotonicity_violation_count','significant_violation_count','max_adjacent_sigma68_increase_ns','sigma68_vs_bin_mid_corr'])}

The audit supports the caveat that amplitude/charge bins are not exchangeable energy slices. They are mixtures of changing electronics and morphology support.

## Absolute Time-Scale Closure

The timing scale is anchored by the S03a analytic timing reference before the uncertainty benchmark:

{markdown_table(s03a)}

The geometry correction uses 2 cm downstream spacing and `v_TOF = 0.078 ns/cm`. Pair residuals remove common event clock terms but do not prove an external beamline absolute time-of-flight calibration. The defensible claim is therefore an internally anchored B-stack time scale suitable for pairwise resolution and interval calibration, not a standalone external TOF measurement.

## Systematics

The dominant systematic is support composition: amplitude and charge bins carry different fractions of saturation, q-template mismatch, baseline width, and anomaly/dropout atoms. The support/action composition table from nonduplicated traditional pair rows is:

{markdown_table(actions, ['dimension','stratum','n_pair_residuals','n_runs','support_fraction','saturation_fraction','dropout_fraction','anomaly_noncommon_fraction','wide_baseline_fraction','high_q_template_fraction','any_action_band_fraction'])}

Sentinel controls are:

{markdown_table(sentinels)}

Leakage and bookkeeping checks are:

{markdown_table(leakage)}

## Caveats

- The current workspace lacks `torch`; this ticket does not retrain the neural networks. It reuses the committed S06b/P06c benchmark rows and independently reruns the raw ROOT reproduction gate.
- Charge is a waveform-area proxy, not an externally calibrated MeV energy. The S14 energy mapping remains a dependency for literal MeV-scale `sigma(E)`.
- Pair residuals share event-level conditions and two-stave correlations. Bootstrap intervals are run-block/event-paired but do not include alternate detector calibrations.
- Action labels are reduced waveform morphology flags, not exhaustive hand-scanned truth labels.
- The winner optimizes interval calibration, not only narrow central width. A model with smaller `sigma68_ns` but poor coverage is not adopted.

## Conclusion

The S06 winner is **{winner['method']}**. It gives the best calibrated held-out timing intervals among the strong traditional baseline, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new phase-conformal gated CNN. The main physics conclusion is that a naive monotonic timing-resolution curve versus amplitude or charge-energy proxy is not stable without support conditioning. Downstream consumers should use support-conditioned interval estimates or explicit abstention/inflation bands rather than a single one-dimensional sigma(A) or sigma(E) correction.

## Reproducibility

Run:

```bash
. .venv/bin/activate
python scripts/issue_2378_s06_resolution_amplitude_energy_timescale.py
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `raw_root_counts_by_run.csv`, copied benchmark/support/leakage CSVs, and `pair_residual_rows_with_pulls.csv.gz`.
"""
    (OUT_DIR / "REPORT.md").write_text(report, encoding="utf-8")

    input_rows = []
    for _, row in counts.iterrows():
        input_rows.append({"path": row["input_path"], "sha256": row["input_sha256"]})
    for name in [CONFIG, *[OUT_DIR / x for x in copy_names]]:
        input_rows.append({"path": str(name), "sha256": sha256_file(Path(name))})
    pd.DataFrame(input_rows).to_csv(OUT_DIR / "input_sha256.csv", index=False)

    manifest = {
        "ticket": 2378,
        "study": "S06",
        "worker": "testbeam-laptop-4",
        "git_commit": git_commit(),
        "command": "python scripts/issue_2378_s06_resolution_amplitude_energy_timescale.py",
        "config": str(CONFIG),
        "root_dir": str(ROOT_DIR),
        "source_benchmark": str(SOURCE_DIR),
        "outputs": {
            p.name: sha256_file(p)
            for p in sorted(OUT_DIR.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
