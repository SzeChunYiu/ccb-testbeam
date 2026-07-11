#!/usr/bin/env python3
"""Aggregate S24 pulse-shape, PID-feasibility, and calibrated-energy evidence.

This script is intentionally light on retraining. S24A and S24B already ran the
raw ROOT loaders and model panels for the same 640737 selected B-stave pulses.
Here we assert those raw-root reproductions, collect the run-heldout benchmark
tables, and write the ticket-specific S24C report and result manifest.
"""

from __future__ import annotations

import ast
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s24c_1783758004_33451_4b095b91_pid_energy_join.json"


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def as_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return json.loads(df.to_json(orient="records"))


def parse_ci(value: Any) -> List[float]:
    if isinstance(value, list):
        return [float(value[0]), float(value[1])]
    parsed = ast.literal_eval(str(value))
    return [float(parsed[0]), float(parsed[1])]


def md_table(df: pd.DataFrame, columns: Iterable[str]) -> str:
    view = df.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.6g}")
    return view.to_markdown(index=False)


def method_lookup(df: pd.DataFrame, method: str) -> Dict[str, Any]:
    matches = df[df["method"] == method]
    if matches.empty:
        raise AssertionError(f"missing required method: {method}")
    return as_records(matches.head(1))[0]


def main() -> None:
    started = time.time()
    cfg = load_json(CONFIG)

    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s24a_dir = ROOT / cfg["s24a_report_dir"]
    s24b_dir = ROOT / cfg["s24b_report_dir"]
    s15c_dir = ROOT / cfg["s15c_report_dir"]

    s24b_result = load_json(s24b_dir / "result.json")
    s15c_result = load_json(s15c_dir / "result.json")

    pulse_summary_all = pd.read_csv(s24b_dir / "method_summary_all.csv")
    pulse_primary = pd.read_csv(s24b_dir / "primary_method_summary.csv")
    pulse_per_run = pd.read_csv(s24b_dir / "heldout_per_run_metrics.csv")
    proxy_shift = pd.read_csv(s24b_dir / "proxy_shift_bootstrap_cis.csv")
    reproduction_counts = pd.read_csv(s24b_dir / "reproduction_counts_by_run.csv")
    reproduction_match = pd.read_csv(s24b_dir / "reproduction_match_table.csv")

    energy_metrics = pd.read_csv(s24a_dir / "method_metrics.csv")
    energy_per_run = pd.read_csv(s24a_dir / "run_heldout_summary.csv")

    required_methods = cfg["required_pulse_shape_methods"]
    pulse_methods = []
    for method in required_methods:
        pulse_methods.append(method_lookup(pulse_summary_all, method))
    pulse_methods_df = pd.DataFrame(pulse_methods).sort_values("roc_auc", ascending=False)

    selected_pulses = int(reproduction_counts["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    raw_match_pass = bool(reproduction_match["pass"].all())
    if selected_pulses != expected or not raw_match_pass:
        raise AssertionError(
            f"raw reproduction failed: selected={selected_pulses}, expected={expected}, "
            f"table_pass={raw_match_pass}"
        )
    if s24b_result["reproduction"]["selected_pulses"] != expected:
        raise AssertionError("S24B raw-root result.json no longer matches the expected count")

    if s15c_result.get("event_level_pid_truth_join_feasible") is not False:
        raise AssertionError("S15C PID feasibility gate no longer blocks event-level PID join")

    pulse_winner = as_records(pulse_methods_df.head(1))[0]
    best_traditional = method_lookup(pulse_summary_all, "traditional_fisher_gatti_all_features")
    energy_winner_row = energy_metrics.sort_values("res68_frac", ascending=True).head(1).iloc[0]
    energy_winner = {
        "method": energy_winner_row["method"],
        "family": energy_winner_row["family"],
        "n": int(energy_winner_row["n"]),
        "bias_frac": float(energy_winner_row["bias_frac"]),
        "res68_frac": float(energy_winner_row["res68_frac"]),
        "res68_ci95": parse_ci(energy_winner_row["res68_ci95"]),
        "mae_mev": float(energy_winner_row["mae_mev"]),
        "mae_mev_ci95": parse_ci(energy_winner_row["mae_mev_ci95"]),
    }

    primary_per_run = pulse_per_run[pulse_per_run["method"].isin(required_methods)].copy()

    artifacts = {
        "s24_pulse_shape_method_benchmark.csv": pulse_methods_df,
        "s24_pulse_shape_per_run.csv": primary_per_run,
        "energy_method_benchmark.csv": energy_metrics,
        "energy_run_heldout_summary.csv": energy_per_run,
        "composition_proxy_shift_cis.csv": proxy_shift,
        "raw_reproduction_counts_by_run.csv": reproduction_counts,
        "raw_reproduction_match_table.csv": reproduction_match,
    }
    for name, df in artifacts.items():
        df.to_csv(out_dir / name, index=False)

    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - started, 3),
        "python": platform.python_version(),
        "raw_reproduction": {
            "source": str(s24b_dir / "reproduction_counts_by_run.csv"),
            "raw_root_source": s24b_result.get("raw_root_dir", "data/root/root"),
            "selected_pulses": selected_pulses,
            "expected_selected_pulses": expected,
            "delta": selected_pulses - expected,
            "passed": selected_pulses == expected and raw_match_pass,
            "samples_per_channel": s24b_result["reproduction"].get("samples_per_channel"),
        },
        "split": s24b_result["split"],
        "label": s24b_result["label"],
        "external_pid_join_status": "blocked_no_event_native_external_pid_branch",
        "external_pid_join_evidence": {
            "source": str(s15c_dir / "result.json"),
            "event_level_pid_truth_join_feasible": False,
            "joined_truth_rows": int(s15c_result.get("joined_truth_rows", 0)),
            "reason": s15c_result["winner"]["reason"],
        },
        "calibrated_energy_join_status": "attached_from_s24a_geant4_birks_bridge",
        "pulse_shape_winner": pulse_winner,
        "energy_winner": energy_winner,
        "best_traditional": best_traditional,
        "required_method_panel": as_records(pulse_methods_df),
        "proxy_shift_bootstrap_cis": as_records(proxy_shift),
        "winner": pulse_winner["method"],
        "winner_metric": "heldout run-block bootstrap ROC AUC",
        "novel_ticket_appended": None,
    }
    write_json(out_dir / "result.json", result)

    report = build_report(cfg, result, pulse_methods_df, primary_per_run, energy_metrics, proxy_shift)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    manifest_payload = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": result["git_commit"],
        "inputs": {
            "s24a_report_dir": cfg["s24a_report_dir"],
            "s24b_report_dir": cfg["s24b_report_dir"],
            "s15c_report_dir": cfg["s15c_report_dir"],
            "config": str(CONFIG.relative_to(ROOT)),
        },
        "artifacts": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            manifest_payload["artifacts"][path.name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    write_json(out_dir / "manifest.json", manifest_payload)

    # Rehash manifest after writing it once so the manifest entry is not stale.
    manifest_payload["artifacts"]["manifest.json"] = {
        "bytes": (out_dir / "manifest.json").stat().st_size,
        "sha256": sha256(out_dir / "manifest.json"),
    }
    write_json(out_dir / "manifest.json", manifest_payload)

    print(f"wrote {out_dir.relative_to(ROOT)}")
    print(f"winner={pulse_winner['method']} roc_auc={pulse_winner['roc_auc']:.6f}")
    print(f"raw_selected_pulses={selected_pulses} expected={expected}")


def build_report(
    cfg: Dict[str, Any],
    result: Dict[str, Any],
    pulse_methods: pd.DataFrame,
    pulse_per_run: pd.DataFrame,
    energy_metrics: pd.DataFrame,
    proxy_shift: pd.DataFrame,
) -> str:
    split = result["split"]
    label = result["label"]
    pulse_winner = result["pulse_shape_winner"]
    energy_winner = result["energy_winner"]

    per_run_winner = pulse_per_run[pulse_per_run["method"] == pulse_winner["method"]]
    per_run_table = per_run_winner.sort_values("run")

    energy_show = energy_metrics.copy()
    energy_show["res68_ci95_low"] = energy_show["res68_ci95"].map(lambda x: parse_ci(x)[0])
    energy_show["res68_ci95_high"] = energy_show["res68_ci95"].map(lambda x: parse_ci(x)[1])
    energy_show = energy_show.sort_values("res68_frac")

    method_table = md_table(
        pulse_methods,
        ["method", "role", "family", "n", "positives", "roc_auc", "auc_ci_low", "auc_ci_high", "average_precision"],
    )
    run_table = md_table(
        per_run_table,
        ["run", "n", "positives", "roc_auc", "average_precision"],
    )
    energy_table = md_table(
        energy_show,
        ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95_low", "res68_ci95_high", "mae_mev"],
    )
    proxy_table = md_table(
        proxy_shift,
        ["metric", "interpretation", "high_minus_low_median_shift", "ci_low", "ci_high", "bootstrap_replicates"],
    )

    return f"""# S24C PID and Calibrated-Energy Composition Bridge

Ticket: `{cfg['ticket_id']}`  
Worker: `{cfg['worker']}`  
Claimed ticket title: Attach external beamline PID and calibrated energy labels to S24 pulse-shape predictions to separate waveform-timing transfer from species and energy-composition effects.

## Abstract

This study attaches the defensible composition information available for the S24 pulse-shape benchmark. The S24B raw ROOT loader reproduces the selected B-stave pulse count exactly, `N_sel = {result['raw_reproduction']['selected_pulses']}`, and the S24B run-heldout pulse-shape panel is carried forward with bootstrap confidence intervals. The pulse-shape winner is `{pulse_winner['method']}` with heldout ROC AUC {pulse_winner['roc_auc']:.6f} [{pulse_winner['auc_ci_low']:.6f}, {pulse_winner['auc_ci_high']:.6f}]. The calibrated-energy bridge is attached from S24A; its best method is `{energy_winner['method']}` with fractional 68 percent resolution {energy_winner['res68_frac']:.6f} [{energy_winner['res68_ci95'][0]:.6f}, {energy_winner['res68_ci95'][1]:.6f}].

The external PID part is intentionally not over-claimed. The prior S15C schema audit found no event-native, run/event-keyed PID, truth, species, Cherenkov, time-of-flight, or beamline tag branch joinable to the HRD waveform rows. Therefore S24C records `external_pid_join_status = blocked_no_event_native_external_pid_branch`: beamline-proxy PID support is available for composition stress tests, but event-level species labels are not attached.

## Raw ROOT Reproduction

The inherited S24B raw ROOT pass reads the B-stack `HRD`/`HRDv` waveform trees and applies the same selected-pulse definition used by the report family. For each candidate pulse, the reconstructed baseline is

`b_rec = median(x_0, x_1, x_2, x_3)`

and the baseline-subtracted pulse amplitude is

`a = max_t (x_t - b_rec)`.

A B-stave pulse is selected when `a > 1000 ADC`. Summing selected pulses by run gives

`N_sel = sum_run N_sel(run) = {result['raw_reproduction']['selected_pulses']}`.

The expected value is `{result['raw_reproduction']['expected_selected_pulses']}`, so the reproduction delta is `{result['raw_reproduction']['delta']}`. The run-count table is written to `raw_reproduction_counts_by_run.csv`, and the exact match assertion is written to `raw_reproduction_match_table.csv`.

## Labels, Split, and Inference Target

S24B defines a run-local pedestal-drift target rather than a particle-species target:

`y = 1[ |b - median_run,stave(b)| >= q_0.80 ]`.

The fitted high-drift threshold is `{label['threshold_adc']} ADC`. Training rows: `{split['train_rows']}`. Heldout rows: `{split['heldout_rows']}`. Heldout runs: `{split['heldout_runs']}`. Confidence intervals use `{split['bootstrap_replicates']}` run-block bootstrap replicates, preserving the run split as the unit of transfer stress.

This target is useful for timing and waveform-transfer stress because it asks whether pulse-shape models can recognize baseline-dependent shape changes on runs not used for training. It is not a replacement for event-level species PID.

## Model Panel

The benchmark includes a strong traditional engineered-feature method, a linear ML baseline, tree boosting, a multilayer perceptron, a 1D convolutional neural network, and a new residual squeeze CNN architecture. The primary heldout metric is ROC AUC with bootstrap confidence intervals.

{method_table}

The best traditional method is `traditional_fisher_gatti_all_features`, with ROC AUC {result['best_traditional']['roc_auc']:.6f} [{result['best_traditional']['auc_ci_low']:.6f}, {result['best_traditional']['auc_ci_high']:.6f}]. The best overall method is `{pulse_winner['method']}`. Relative to the traditional Fisher/Gatti panel, the absolute heldout AUC gain is {pulse_winner['roc_auc'] - result['best_traditional']['roc_auc']:.6f}.

## Winner Per-Run Behavior

The winner's heldout performance by run is:

{run_table}

The spread across heldout runs is a material systematic, not a nuisance to average away. It reflects changing beam, pedestal, and amplitude-composition conditions that a transferable waveform model must tolerate.

## Calibrated Energy Bridge

S24A provides the calibrated-energy benchmark for the same selected-pulse family. The traditional Geant4-Birks method models charge saturation as

`Q = alpha E_dep / (1 + k_B dE/dx)`

and applies the inverse bridge

`E_cal = Q (1 + k_B dE/dx) / alpha`.

The energy-composition benchmark is:

{energy_table}

The calibrated-energy winner is `{energy_winner['method']}` with fractional 68 percent resolution {energy_winner['res68_frac']:.6f} and 95 percent bootstrap CI [{energy_winner['res68_ci95'][0]:.6f}, {energy_winner['res68_ci95'][1]:.6f}]. This is attached as an energy-composition bridge, not as an event-level truth label.

## Composition Proxy Shifts

Because event-native external PID is absent, S24C uses S24B's proxy shift table to quantify how the high-drift prediction target co-varies with timing, energy-amplitude, and PID-like residual proxies on heldout runs.

{proxy_table}

The energy proxy shift is the high-minus-low median shift in log10 amplitude residual. The PID proxy is the odd-negative ADC residual used by S24B as a species/composition-sensitive stress variable. These are proxy diagnostics only: they support sensitivity analysis, but they do not identify individual particle species.

## Systematics and Caveats

1. Raw selection systematic: the selected-pulse count is exactly reproduced from the S24B raw ROOT loader, but S24C itself is an aggregation layer and does not retrain the full waveform panel.
2. Run split systematic: all reported pulse-shape CIs come from heldout runs `[42, 50, 57, 58, 60, 62, 64, 65]`, so the interval covers run transfer better than random row splitting.
3. PID limitation: no audited raw HRD source exposes event-level PID/truth/species labels with joinable run and event keys. Any event-level species-conditioned conclusion would require new beamline PID data or a new calibrated join table.
4. Energy limitation: calibrated energy is attached through S24A's benchmark bridge. It separates amplitude/energy-composition effects at method level, but it is not an external particle label.
5. Model selection limitation: the residual squeeze CNN is the new architecture in the S24B panel; it improves the neural architecture family but does not beat gradient-boosted trees on the heldout transfer metric.

## Conclusion

S24C names `{pulse_winner['method']}` as the S24 pulse-shape winner and `{energy_winner['method']}` as the calibrated-energy winner. The analysis separates three things that were previously easy to conflate: waveform/pedestal transfer is benchmarked directly, calibrated-energy composition is attached through S24A, and external event-level PID remains blocked by the raw ROOT schema. The requested species-conditioned PID attachment cannot be made honestly with the current mirrored data.
"""


if __name__ == "__main__":
    main()
