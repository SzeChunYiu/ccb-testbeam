#!/usr/bin/env python3
"""S26c PID-aware pulse-shape timing transfer benchmark."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def configured_runs(cfg: dict[str, Any]) -> list[int]:
    runs: list[int] = []
    for values in cfg["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_to_group(cfg: dict[str, Any]) -> dict[int, str]:
    out: dict[int, str] = {}
    for group, runs in cfg["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def recount_raw_root(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_dir = ROOT / cfg["raw_root_dir"]
    baseline_idx = np.asarray(cfg["baseline_samples"], dtype=int)
    channels = np.asarray(list(cfg["staves"].values()), dtype=int)
    nsamp = int(cfg["samples_per_channel"])
    run_group = run_to_group(cfg)
    rows = []
    for run in configured_runs(cfg):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        events = 0
        selected = 0
        per_stave = {name: 0 for name in cfg["staves"]}
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            ped = np.median(raw[:, :, baseline_idx], axis=-1)
            corrected = raw - ped[:, :, None]
            amp = corrected[:, channels, :].max(axis=-1)
            mask = amp > float(cfg["amplitude_cut_adc"])
            events += int(len(raw))
            selected += int(mask.sum())
            for i, name in enumerate(cfg["staves"]):
                per_stave[name] += int(mask[:, i].sum())
        row = {"run": run, "group": run_group[run], "events": events, "selected_pulses": selected}
        row.update(per_stave)
        rows.append(row)
    counts = pd.DataFrame(rows)
    checks = [
        {
            "quantity": "total selected B-stave pulses",
            "expected": int(cfg["expected_selected_pulses"]),
            "reproduced": int(counts["selected_pulses"].sum()),
        }
    ]
    for group, expected in cfg["expected_group_counts"].items():
        got = int(counts.loc[counts["group"] == group, "selected_pulses"].sum())
        checks.append({"quantity": f"{group} selected pulses", "expected": int(expected), "reproduced": got})
    match = pd.DataFrame(checks)
    match["delta"] = match["reproduced"] - match["expected"]
    match["tolerance"] = 0
    match["pass"] = match["delta"].eq(0)
    return counts, match


def parse_ci(value: Any) -> tuple[float, float]:
    if isinstance(value, (list, tuple)):
        return float(value[0]), float(value[1])
    parsed = ast.literal_eval(str(value))
    return float(parsed[0]), float(parsed[1])


def load_sources(cfg: dict[str, Any]) -> dict[str, Any]:
    pid_energy = ROOT / cfg["sources"]["pid_energy"]
    timing = ROOT / cfg["sources"]["timing"]
    pileup = ROOT / cfg["sources"]["pileup"]
    pedestal = ROOT / cfg["sources"]["pedestal"]
    return {
        "joint": pd.read_csv(pid_energy / "joint_method_benchmark.csv"),
        "pid": pd.read_csv(pid_energy / "pid_method_benchmark.csv"),
        "energy": pd.read_csv(pid_energy / "energy_method_benchmark.csv"),
        "timing": pd.read_csv(timing / "method_metrics.csv"),
        "timing_by_run": pd.read_csv(timing / "per_run_metrics.csv"),
        "pileup": pd.read_csv(pileup / "method_metrics.csv"),
        "pedestal": pd.read_csv(pedestal / "method_summary.csv"),
        "source_results": {
            name: read_json(ROOT / rel / "result.json")
            for name, rel in cfg["sources"].items()
            if (ROOT / rel / "result.json").exists()
        },
    }


def row_one(df: pd.DataFrame, column: str, value: str, context: str) -> pd.Series:
    rows = df[df[column] == value]
    if rows.empty:
        raise KeyError(f"{context}: missing {value!r} in {column}")
    return rows.iloc[0]


def bootstrap_timing_by_run(timing_by_run: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    pool_df = timing_by_run[timing_by_run["pool"] == "cfd0.20_cut1000"].copy()
    for method, group in pool_df.groupby("method"):
        runs = np.asarray(sorted(group["run"].unique()), dtype=int)
        by_run = group.set_index("run")
        values = np.asarray([by_run.loc[run, "robust_width_ns"] for run in runs], dtype=float)
        weights = np.asarray([by_run.loc[run, "n_pairs"] for run in runs], dtype=float)
        est = float(np.average(values, weights=weights))
        boot = []
        for _ in range(int(n_boot)):
            sample = rng.choice(np.arange(len(runs)), size=len(runs), replace=True)
            boot.append(float(np.average(values[sample], weights=weights[sample])))
        lo, hi = np.quantile(boot, [0.025, 0.975])
        rows.append({"method": method, "run_weighted_width_ns": est, "run_boot_ci_low_ns": float(lo), "run_boot_ci_high_ns": float(hi), "runs": int(len(runs))})
    return pd.DataFrame(rows)


def build_benchmark(cfg: dict[str, Any], sources: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    timing_boot = bootstrap_timing_by_run(
        sources["timing_by_run"], np.random.default_rng(1783798536), int(cfg["bootstrap_replicates"])
    )
    rows = []
    for method, mapping in cfg["method_map"].items():
        joint = row_one(sources["joint"], "joint_method", method, "joint PID-energy source")
        timing = row_one(sources["timing"], "method", mapping["timing_method"], "timing source")
        timing_ci = row_one(timing_boot, "method", mapping["timing_method"], "timing bootstrap")
        pileup = row_one(sources["pileup"], "method", mapping["pileup_method"], "pileup source")
        pedestal_rows = sources["pedestal"]
        pedestal_penalty = 0.0
        if "method" in pedestal_rows.columns and mapping["pedestal_method"] in set(pedestal_rows["method"]):
            prow = row_one(pedestal_rows, "method", mapping["pedestal_method"], "pedestal source")
            for candidate in ["pedestal_flip_fraction", "label_flip_fraction", "shape_l2_median", "score"]:
                if candidate in prow.index and np.isfinite(float(prow[candidate])):
                    pedestal_penalty = abs(float(prow[candidate]))
                    break
        weights = cfg["score_weights"]
        norm = cfg["normalizers"]
        score = (
            weights["pid_auc_loss"] * (1.0 - float(joint["pid_auc"]))
            + weights["pid_ap_loss"] * (1.0 - float(joint["pid_average_precision"]))
            + weights["timing_sigma68_norm"] * float(timing["robust_width_ns"]) / float(norm["timing_sigma68_ns"])
            + weights["pileup_ap_loss"] * (1.0 - float(pileup["detection_ap"]))
            + weights["pileup_timing_sigma68_norm"] * float(pileup["time_sigma68_ns"]) / float(norm["pileup_timing_sigma68_ns"])
            + weights["saturation_energy_sigma68"] * float(joint["saturation_res68_frac"])
            + weights["pedestal_shape_penalty"] * pedestal_penalty / float(norm["pedestal_shape_penalty"])
            + weights["energy_sigma68"] * float(joint["energy_res68_frac"])
            + weights["energy_bias_abs"] * abs(float(pileup["energy_fractional_bias"]))
        )
        rows.append(
            {
                "method": method,
                "family": mapping["family"],
                "pid_auc": float(joint["pid_auc"]),
                "pid_auc_ci_low": float(joint["pid_auc_ci_low"]),
                "pid_auc_ci_high": float(joint["pid_auc_ci_high"]),
                "pid_average_precision": float(joint["pid_average_precision"]),
                "timing_sigma68_ns": float(timing["robust_width_ns"]),
                "timing_sigma68_ci_low_ns": float(timing["robust_ci_low_ns"]),
                "timing_sigma68_ci_high_ns": float(timing["robust_ci_high_ns"]),
                "timing_run_boot_ci_low_ns": float(timing_ci["run_boot_ci_low_ns"]),
                "timing_run_boot_ci_high_ns": float(timing_ci["run_boot_ci_high_ns"]),
                "pileup_detection_ap": float(pileup["detection_ap"]),
                "pileup_detection_ap_ci_low": float(pileup["detection_ap_ci_low"]),
                "pileup_detection_ap_ci_high": float(pileup["detection_ap_ci_high"]),
                "pileup_time_sigma68_ns": float(pileup["time_sigma68_ns"]),
                "pileup_time_sigma68_ci_low_ns": float(pileup["time_sigma68_ns_ci_low"]),
                "pileup_time_sigma68_ci_high_ns": float(pileup["time_sigma68_ns_ci_high"]),
                "saturation_energy_res68": float(joint["saturation_res68_frac"]),
                "saturation_energy_res68_ci_low": float(joint["saturation_res68_ci_low"]),
                "saturation_energy_res68_ci_high": float(joint["saturation_res68_ci_high"]),
                "pedestal_shape_penalty": float(pedestal_penalty),
                "energy_res68": float(joint["energy_res68_frac"]),
                "energy_res68_ci_low": float(joint["energy_res68_ci_low"]),
                "energy_res68_ci_high": float(joint["energy_res68_ci_high"]),
                "energy_bias_abs": abs(float(pileup["energy_fractional_bias"])),
                "joint_loss": float(score),
            }
        )
    return pd.DataFrame(rows).sort_values("joint_loss").reset_index(drop=True), timing_boot


def md_table(df: pd.DataFrame, columns: list[str]) -> str:
    sub = df[columns].copy()
    def fmt(x: Any) -> str:
        if isinstance(x, float):
            if not math.isfinite(x):
                return "nan"
            return f"{x:.6g}"
        return str(x)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(fmt(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_report(out: Path, cfg: dict[str, Any], match: pd.DataFrame, benchmark: pd.DataFrame, sources: dict[str, Any], manifest: dict[str, Any]) -> None:
    winner = benchmark.iloc[0]
    report = f"""# S26c PID-aware pulse-shape timing transfer study

**Ticket:** `{cfg['ticket_id']}`  
**Worker:** `{cfg['worker']}`  
**Raw ROOT directory:** `{cfg['raw_root_dir']}`  
**Command:** `{cfg['command']}`  
**Git commit:** `{manifest['git_commit']}`

## Abstract

This study asks whether PID-aware pulse-shape information improves timing,
pile-up localization, saturation recovery, pedestal stability, and calibrated
energy transfer across run families. The benchmark compares a strong
traditional charge-ratio/template/timewalk method against ridge, gradient
boosted trees, MLP, 1D-CNN, and a new residual architecture. The machine
readable winner in `result.json` is **`{winner['method']}`** with joint loss
`{winner['joint_loss']:.6f}`.

## Raw ROOT reproduction

The raw gate reads each `h101/HRDv` array from `data/root/root/hrdb_run_NNNN.root`,
reshapes events into eight channels by eighteen samples, subtracts

`b_{{e,c}} = median(x_{{e,c,t}} : t in {{0,1,2,3}})`,

and counts B2/B4/B6/B8 pulses satisfying

`max_t (x_{{e,c,t}} - b_{{e,c}}) > 1000 ADC`.

{md_table(match, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'])}

The exact raw ROOT reproduction is a hard precondition for interpreting all
downstream benchmark tables.

## Split and bootstrap design

All source endpoints use held-out run families rather than shuffled events.
The calibration groups are Sample I calibration runs 31-37 and 39-42 plus
Sample II calibration run 64. The analysis groups are Sample I runs 44-57 and
Sample II runs 58-63 and 65. Timing CIs in this ticket are recomputed by
resampling held-out runs with replacement; inherited PID, pile-up, saturation,
and energy CIs are source run-block percentile intervals.

## Methods

The traditional method combines charge-depth PID cuts, template-shape
consistency, constrained monotone timewalk correction, and two-pulse
CFD/template residual fitting. Ridge and GBT operate on standardized pulse,
charge, timing, and shape atoms. The MLP is a dense nonlinear model on the same
summary space. The 1D-CNN operates directly on ordered 18-sample waveforms. The
new architecture is a residual family: action-gated residual ensemble for PID,
physics-residual MLP for energy, gated residual CNN for timing, and boosted
template residual stack for pile-up.

## Score

Lower is better. The registered loss is

`L = 0.18(1-AUC_PID) + 0.08(1-AP_PID) + 0.18 sigma_t/2.5 + 0.13(1-AP_pileup) + 0.10 sigma_pileup/12 + 0.12 r_sat + 0.06 P_ped + 0.10 r_E + 0.05 |bias_E|`.

Here `sigma_t` is the robust run-heldout timing width, `sigma_pileup` is the
pile-up timing sigma68, `r_sat` is saturation-stratum energy res68, `P_ped` is
the available pedestal shape penalty, and `r_E` is global energy res68.

## Head-to-head benchmark

{md_table(benchmark, ['method', 'family', 'joint_loss', 'pid_auc', 'pid_average_precision', 'timing_sigma68_ns', 'pileup_detection_ap', 'pileup_time_sigma68_ns', 'saturation_energy_res68', 'energy_res68'])}

## Confidence intervals

{md_table(benchmark, ['method', 'timing_sigma68_ci_low_ns', 'timing_sigma68_ci_high_ns', 'timing_run_boot_ci_low_ns', 'timing_run_boot_ci_high_ns', 'pileup_detection_ap_ci_low', 'pileup_detection_ap_ci_high', 'energy_res68_ci_low', 'energy_res68_ci_high'])}

## Systematics

PID is a beamline/range enriched proxy, not hidden particle truth. The
traditional PID endpoint is therefore structurally aligned with that proxy, and
perfect AUC should be read as closure on the available support rather than
absolute PID efficiency. Energy uses duplicate-readout and GEANT4/Birks
calibration priors; it is a transfer-calibrated energy endpoint, not a direct
calorimeter truth label. Timing is evaluated on run-heldout pulse pairs in the
high-support `cfd0.20_cut1000` gate. Pile-up stress is synthetic-plus-empirical
and has only 600 labelled events, so AP differences at the third decimal place
are not scientifically material.

## Caveats

The source tasks are independently trained endpoint studies; this script
performs a ticket-local synthesis and timing bootstrap rather than fitting a
single monolithic multi-task neural network. That is deliberate: without
event-aligned true PID and energy labels, a multi-task model would mostly learn
proxy construction rules. The best next experiment is therefore a digitized
GEANT4 multi-task benchmark with true event labels, which is the single novel
ticket proposed in `result.json`.

## Reproducibility

Primary outputs are `result.json`, `REPORT.md`, `manifest.json`,
`reproduction_counts_by_run.csv`, `reproduction_match_table.csv`,
`method_benchmark.csv`, `timing_run_bootstrap.csv`, and copied source metric
tables. The source artifact directories are:

- PID/energy: `{cfg['sources']['pid_energy']}`
- Timing: `{cfg['sources']['timing']}`
- Pile-up: `{cfg['sources']['pileup']}`
- Pedestal: `{cfg['sources']['pedestal']}`
"""
    out.joinpath("REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    start = time.time()
    cfg_path = Path(args.config)
    cfg = read_json(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    counts, match = recount_raw_root(cfg)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    sources = load_sources(cfg)
    benchmark, timing_boot = build_benchmark(cfg, sources)
    winner = benchmark.iloc[0].to_dict()

    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    benchmark.to_csv(out / "method_benchmark.csv", index=False)
    timing_boot.to_csv(out / "timing_run_bootstrap.csv", index=False)
    sources["pid"].to_csv(out / "source_pid_method_benchmark.csv", index=False)
    sources["energy"].to_csv(out / "source_energy_method_benchmark.csv", index=False)
    sources["timing"].to_csv(out / "source_timing_method_metrics.csv", index=False)
    sources["pileup"].to_csv(out / "source_pileup_method_metrics.csv", index=False)

    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "winner": winner["method"],
        "winner_details": winner,
        "raw_root_reproduction": {
            "raw_root_dir": cfg["raw_root_dir"],
            "passed": bool(match["pass"].all()),
            "table": match.to_dict(orient="records"),
        },
        "split": {"type": "complete run-family holdout", "run_groups": cfg["run_groups"]},
        "bootstrap": {"unit": "held-out run block", "replicates": int(cfg["bootstrap_replicates"]), "interval": "95% percentile"},
        "method_benchmark": benchmark.to_dict(orient="records"),
        "novel_tickets_appended": [
            {
                "title": "Digitized GEANT4 multi-task PID-energy-timing truth benchmark",
                "body": "Generate ADC-like waveforms with true event-aligned PID, deposited energy, timing, pile-up, saturation, and pedestal labels to test whether a coupled neural architecture beats the physics baseline without proxy-label circularity."
            }
        ],
        "runtime_sec": time.time() - start,
    }
    (out / "result.json").write_text(json.dumps(clean_json(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "command": cfg["command"],
        "config": str(cfg_path),
        "raw_root_dir": cfg["raw_root_dir"],
        "source_artifacts": cfg["sources"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
        "outputs": [],
    }
    write_report(out, cfg, match, benchmark, sources, manifest)
    for path in sorted(out.iterdir()):
        if path.is_file():
            manifest["outputs"].append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    (out / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket_id": cfg["ticket_id"], "winner": winner["method"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
