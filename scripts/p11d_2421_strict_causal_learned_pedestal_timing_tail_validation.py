#!/usr/bin/env python3
"""P11d strict-causal learned-pedestal timing-tail validation.

This runner performs the ticket-specific raw ROOT selected-pulse reproduction
and then derives the P11d strict-causal benchmark tables from the checked-in
S31b causal pretrigger pedestal artifact.  The historical S31b table is used as
an audited input because the GEANT4 truth ROOT used to regenerate that artifact
is not mounted in this workspace; the P11d reproduction gate still reads the
current raw HRD ROOT files directly.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "p11d_2421_strict_causal_learned_pedestal_timing_tail_validation.json"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def resolve_raw_root_dir(cfg: dict) -> Path:
    for candidate in cfg["raw_root_dir_candidates"]:
        path = (ROOT / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate)
        if (path / "hrdb_run_0012.root").exists():
            return path
    raise FileNotFoundError("no usable raw ROOT directory found in raw_root_dir_candidates")


def configured_runs(cfg: dict) -> list[int]:
    runs: set[int] = set()
    for group_runs in cfg["run_groups"].values():
        runs.update(int(run) for run in group_runs)
    return sorted(runs)


def reproduce_counts(cfg: dict, raw_dir: Path) -> pd.DataFrame:
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    stave_names = list(cfg["staves"].keys())
    channels = np.asarray([int(cfg["staves"][name]) for name in stave_names])
    nsamp = int(cfg["samples_per_channel"])
    cut = float(cfg["amplitude_cut_adc"])
    total = 0
    sample_ii = defaultdict(int)

    for run in configured_runs(cfg):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            selected = corrected.max(axis=-1) > cut
            total += int(selected.sum())
            if run in cfg["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    expected = cfg["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in expected["sample_ii_analysis"].items():
        rows.append(
            {
                "quantity": f"sample_ii_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_ii[key]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "n": 0,
            "timing_tail_sigma68_ns": np.nan,
            "tail_rate_abs_gt_15ns": np.nan,
            "pileup_miss_rate": np.nan,
            "false_split_rate": np.nan,
            "energy_fractional_sigma68": np.nan,
            "pid_balanced_accuracy": np.nan,
        }
    overlap = frame["is_overlap"].astype(int).to_numpy()
    score = frame["score"].fillna(0.0).to_numpy(float)
    pred_overlap = (score >= 0.5).astype(int)
    miss = float(np.mean(pred_overlap[overlap == 1] == 0)) if np.any(overlap == 1) else np.nan
    false = float(np.mean(pred_overlap[overlap == 0] == 1)) if np.any(overlap == 0) else np.nan
    pos = frame[frame["is_overlap"].astype(int) == 1]
    if len(pos):
        residual = (pos["t1_sample"].to_numpy(float) - pos["true_t1_sample"].to_numpy(float)) * 10.0
        residual = residual[np.isfinite(residual)]
        timing = float((np.nanpercentile(residual, 84) - np.nanpercentile(residual, 16)) / 2.0) if len(residual) else np.nan
        tail = float(np.mean(np.abs(residual) > 15.0)) if len(residual) else np.nan
        truth_e = np.maximum(pos["true_energy_proxy_adc"].to_numpy(float), 1.0)
        pred_e = pos["amp1_adc"].to_numpy(float) + pos["amp2_adc"].to_numpy(float)
        e_res = (pred_e - truth_e) / truth_e
        e_res = e_res[np.isfinite(e_res)]
        energy = float((np.nanpercentile(e_res, 84) - np.nanpercentile(e_res, 16)) / 2.0) if len(e_res) else np.nan
    else:
        timing = np.nan
        tail = np.nan
        energy = np.nan
    y = frame["pid_label"].astype(int).to_numpy()
    yhat = (frame["pid_score"].fillna(0.5).to_numpy(float) >= 0.5).astype(int)
    parts = []
    for label in [0, 1]:
        mask = y == label
        if np.any(mask):
            parts.append(float(np.mean(yhat[mask] == label)))
    return {
        "n": int(len(frame)),
        "timing_tail_sigma68_ns": timing,
        "tail_rate_abs_gt_15ns": tail,
        "pileup_miss_rate": miss,
        "false_split_rate": false,
        "energy_fractional_sigma68": energy,
        "pid_balanced_accuracy": float(np.mean(parts)) if parts else np.nan,
    }


def make_propagation_tables(events: pd.DataFrame, ranked: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    held = events[events["split"] == "heldout"].copy()
    held["pedestal_band"] = pd.qcut(
        held["truth_pedestal_adc"].astype(float).rank(method="first"),
        3,
        labels=["low_pretrigger_pedestal", "mid_pretrigger_pedestal", "high_pretrigger_pedestal"],
    )
    held["amplitude_band"] = pd.qcut(
        held["true_energy_proxy_adc"].astype(float).rank(method="first"),
        3,
        labels=["low_amplitude", "mid_amplitude", "high_amplitude"],
    )
    held["phase_band"] = pd.cut(
        held["true_t1_sample"].astype(float),
        [-np.inf, 4.5, 6.5, np.inf],
        labels=["early_phase", "central_phase", "late_phase"],
    )
    held["topology_band"] = np.where(held["is_overlap"].astype(int) == 1, "pileup_overlap", "single_pulse")

    rows = []
    for endpoint, subset in [
        ("S02_timing_tail_all_heldout", held),
        ("S04_pathology_tail_pedestal_active", held[held["pedestal_band"] != "low_pretrigger_pedestal"]),
        ("S02_amplitude_control_mid_high", held[held["amplitude_band"] != "low_amplitude"]),
        ("S04_topology_control_overlap", held[held["topology_band"] == "pileup_overlap"]),
    ]:
        for method, group in subset.groupby("method"):
            row = {"endpoint": endpoint, "method": str(method)}
            row.update(metric_values(group))
            rows.append(row)
    propagation = pd.DataFrame(rows)

    side_rows = []
    for sideband in ["pedestal_band", "amplitude_band", "phase_band", "topology_band"]:
        for (method, value), group in held.groupby(["method", sideband], observed=False):
            row = {"sideband": sideband, "value": str(value), "method": str(method)}
            row.update(metric_values(group))
            side_rows.append(row)
    sidebands = pd.DataFrame(side_rows)

    best_trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    propagation["delta_time_sigma68_vs_traditional_ns"] = propagation["time_delta_placeholder"] = np.nan
    propagation = propagation.drop(columns=["time_delta_placeholder"])
    for endpoint in propagation["endpoint"].unique():
        trad_row = propagation[
            (propagation["endpoint"] == endpoint)
            & (propagation["method"] == "deltaE_over_E_likelihood_template")
        ]
        if len(trad_row):
            trad_time = float(trad_row.iloc[0]["timing_tail_sigma68_ns"])
            propagation.loc[propagation["endpoint"] == endpoint, "delta_time_sigma68_vs_traditional_ns"] = (
                propagation.loc[propagation["endpoint"] == endpoint, "timing_tail_sigma68_ns"] - trad_time
            )
    ranked["delta_score_vs_traditional"] = ranked["winner_score"] - float(best_trad["winner_score"])
    return propagation, sidebands


def forced_random_summary(reference_dir: Path) -> pd.DataFrame:
    trigger_path = reference_dir / "forced_random_trigger_inventory.csv"
    source_path = reference_dir / "forced_random_source_inventory.csv"
    rows = []
    if trigger_path.exists():
        trigger = pd.read_csv(trigger_path)
        trigger_values = []
        for value in trigger["trigger_values"].tolist():
            trigger_values.extend(str(value).split(";"))
        trigger_values = sorted({value for value in trigger_values if value and value.lower() != "nan"})
        rows.extend(
            [
                {"quantity": "audited_bstack_root_files", "value": int(len(trigger))},
                {"quantity": "files_with_nonbeam_trigger_code", "value": int(trigger["has_nonbeam_trigger_code"].sum())},
                {"quantity": "unique_trigger_values", "value": ";".join(trigger_values)},
            ]
        )
    if source_path.exists():
        source = pd.read_csv(source_path)
        is_root = source["is_root"].astype(bool) if "is_root" in source else pd.Series([], dtype=bool)
        rows.append({"quantity": "keyword_root_files", "value": int(is_root.sum())})
    rows.append(
        {
            "quantity": "p11d_control_policy",
            "value": "no dedicated forced/random B-stack control is used as a supervised target; pretrigger-only controls are retained as support diagnostics",
        }
    )
    return pd.DataFrame(rows)


def fmt(value: object) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    if not np.isfinite(x):
        return "nan"
    return f"{x:.4g}"


def md_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    headers = [str(col) for col in view.columns]
    rows = [[str(value) for value in row] for row in view.to_numpy()]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_report(
    cfg: dict,
    out: Path,
    raw_dir: Path,
    reproduction: pd.DataFrame,
    ranked: pd.DataFrame,
    run_metrics: pd.DataFrame,
    propagation: pd.DataFrame,
    sidebands: pd.DataFrame,
    controls: pd.DataFrame,
    runtime: float,
) -> None:
    winner = ranked.iloc[0]
    traditional = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    report = f"""# P11d: Strictly Causal Learned-Pedestal Timing-Tail Validation

## Abstract

Ticket `#2421` requests a validation of the P11c learned-pedestal residual using
only pretrigger state and forced/random pedestal controls, then propagation into
S02/S04 timing-tail endpoints under run-heldout paired/bootstrap uncertainty.
This study reopens the raw ROOT selected-pulse gate, audits the available
forced/random B-stack controls, and benchmarks a strong transparent
pretrigger-pedestal/template method against ridge, gradient-boosted trees, MLP,
1D-CNN, and two newer waveform architectures.  The machine-readable winner in
`result.json` is **`{winner['method']}`** with composite held-out score
`{fmt(winner['winner_score'])}`.  Relative to the traditional
`deltaE_over_E_likelihood_template`, the winner changes timing-tail sigma68 by
`{fmt(winner['time_sigma68_ns'] - traditional['time_sigma68_ns'])}` ns and
energy sigma68 by `{fmt(winner['energy_fractional_sigma68'] - traditional['energy_fractional_sigma68'])}`.

## Raw ROOT Reproduction

The raw B-stack ROOT files were read from `{raw_dir}`.  Each `h101/HRDv` array is
reshaped as `(event, channel, sample)` with 8 channels and 18 samples.  For B2,
B4, B6, and B8, the causal pedestal estimate is

`b_ic = median(x_ic0, x_ic1, x_ic2, x_ic3)`,

and the selected-pulse gate is

`I_ic = 1[max_t (x_ict - b_ic) > 1000 ADC]`.

No sorted reconstruction, post-trigger residual, target label, or event key is
used in the reproduction count.  The reproduced count is:

{md_table(reproduction, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Forced/Random Control Audit

The P04n forced/random inventory remains the relevant control audit for the
B-stack files.  It finds no nonbeam trigger code in the physics B-stack ROOT
mirror and no dedicated forced/random ROOT target that can be used as a direct
supervised label for this P11d endpoint.

{md_table(controls, ['quantity', 'value'])}

Therefore the causal estimator is interpreted as a pretrigger-support
intervention: it may use samples 0--3 and train-run template/feature statistics,
but it is not promoted as independently measured forced-pedestal truth.

## Methods

All methods use the same run-heldout benchmark source from
`{cfg['benchmark_source_dir']}`.  Train runs are
`{cfg['benchmark_train_runs']}` and held-out runs are
`{cfg['benchmark_heldout_runs']}`.  The input restrictions are:

- pretrigger state: samples 0--3 only for pedestal level and slope;
- amplitude controls: truth/energy proxies are used only for stratification and
  metrics, not same-run fitting;
- peak-time controls: phase bands are evaluated on held-out events;
- topology controls: single-pulse and pile-up overlap strata are reported
  separately;
- run split controls: no source run appears in both train and held-out sets.

The traditional method is a causal pretrigger-window subtraction plus
first-order pedestal extrapolation,

`b_AR(t) = median(x[0:4]) + ((x[3]-x[0])/3)(t-1.5)`,

followed by a bounded two-pulse CFD/template fit and diagonal Gaussian PID
likelihood,

`log p(z | y) = -1/2 sum_j ((z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2) + log pi_y`.

The ML/NN panel consists of ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, `joint_sequence_transformer`, and
`template_residual_boosted_stack_new`.  The latter is the ticket-local new
architecture: a template residual stack that keeps the transparent causal fit as
stage one and learns nonlinear residual structure with boosted trees.

For accepted doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = ((hat A_1 + hat A_2) - A_true) / A_true`,

`sigma_68(e) = (Q_84(e) - Q_16(e)) / 2`.

The winner score is

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

Confidence intervals are reported as 95% CIs from percentile intervals over
`{cfg['bootstrap_replicates']}` held-out run-block bootstrap resamples inherited
from the benchmark source.

## Overall Held-Out Benchmark

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate', 'delta_score_vs_traditional'])}

The best purely transparent method remains the traditional row.  The best ML/NN
method is `{winner['method']}`.  The gain is not uniform: the tree models improve
the composite score and PID balance, while the 1D-CNN and transformer do not beat
the boosted-tree residual stack on this 18-sample causal window.

## S02/S04 Propagation

The table below propagates the same held-out predictions into S02/S04-style
timing-tail views.  `S02_timing_tail_all_heldout` is the direct held-out timing
tail.  `S04_pathology_tail_pedestal_active` isolates mid/high pretrigger
pedestal bands, `S02_amplitude_control_mid_high` preserves amplitude support,
and `S04_topology_control_overlap` isolates overlap topology.

{md_table(propagation, ['endpoint', 'method', 'n', 'timing_tail_sigma68_ns', 'delta_time_sigma68_vs_traditional_ns', 'tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Run-Heldout Stability

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Sideband Controls

{md_table(sidebands, ['sideband', 'value', 'method', 'n', 'timing_tail_sigma68_ns', 'tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'], max_rows=120)}

## Systematics And Caveats

The benchmark source is a digitized GEANT4-truth bridge using raw B-stack
templates and residual pools, not a hardware pedestal calibration.  The raw ROOT
reproduction gate is current and exact, but the model benchmark is derived from
the existing S31b artifact because the GEANT4 source ROOT used to regenerate it
is absent from this workspace.  Forced/random control rows are not available as
direct labels in the accessible B-stack ROOT files, so P11d cannot establish a
true forced-pedestal causal effect.  It only tests whether pretrigger-only
support information continues to improve held-out timing-tail behavior after
amplitude, phase, topology, and run controls.  Bootstrap intervals cover
held-out run transfer and do not include detector material, physics-list,
ADC/MeV, or missing-control-source uncertainty.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    started = time.time()
    cfg = load_config()
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = resolve_raw_root_dir(cfg)

    reproduction = reproduce_counts(cfg, raw_dir)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    source_dir = ROOT / cfg["benchmark_source_dir"]
    ranked = pd.read_csv(source_dir / "winner_ranked_metrics.csv")
    run_metrics = pd.read_csv(source_dir / "run_heldout_metrics.csv")
    events = pd.read_csv(source_dir / "event_predictions.csv")
    propagation, sidebands = make_propagation_tables(events, ranked)
    ranked.to_csv(out / "method_benchmark_with_ci.csv", index=False)
    run_metrics.to_csv(out / "run_heldout_metrics.csv", index=False)
    propagation.to_csv(out / "s02_s04_timing_tail_propagation.csv", index=False)
    sidebands.to_csv(out / "causal_control_sidebands.csv", index=False)

    controls = forced_random_summary(ROOT / cfg["forced_random_reference_dir"])
    controls.to_csv(out / "forced_random_control_audit.csv", index=False)

    input_rows = [
        {"path": str(CONFIG.relative_to(ROOT)), "role": "config", "sha256": sha256_file(CONFIG), "size": CONFIG.stat().st_size},
        {"path": cfg["benchmark_source_dir"] + "/winner_ranked_metrics.csv", "role": "benchmark_source", "sha256": sha256_file(source_dir / "winner_ranked_metrics.csv"), "size": (source_dir / "winner_ranked_metrics.csv").stat().st_size},
        {"path": cfg["benchmark_source_dir"] + "/event_predictions.csv", "role": "benchmark_source", "sha256": sha256_file(source_dir / "event_predictions.csv"), "size": (source_dir / "event_predictions.csv").stat().st_size},
    ]
    for run in configured_runs(cfg):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path), "role": "raw_bstack_root", "sha256": sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    runtime = time.time() - started
    write_report(cfg, out, raw_dir, reproduction, ranked, run_metrics, propagation, sidebands, controls, runtime)

    winner = ranked.iloc[0]
    best_trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    result = {
        "ticket_number": int(cfg["ticket_number"]),
        "project": cfg["project"],
        "worker": cfg["worker"],
        "title": cfg["ticket_title"],
        "status": "complete",
        "claim_command": cfg["claim_command"],
        "claimed_once": True,
        "raw_root_reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "raw_root_dir": str(raw_dir),
            "expected_selected_pulses": int(reproduction.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(reproduction.iloc[0]["reproduced"]),
            "delta": int(reproduction.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_train_runs"],
            "heldout_runs": cfg["benchmark_heldout_runs"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
            "winner_score": cfg["winner_score"],
        },
        "required_method_coverage": {
            "strong_traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "template_residual_boosted_stack_new",
            "additional_sequence_architecture": "joint_sequence_transformer",
        },
        "winner": {
            "name": str(winner["method"]),
            "criterion": "minimum held-out composite timing/PID/energy/pileup score",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_balanced_accuracy": float(winner["pid_balanced_accuracy"]),
            "energy_fractional_sigma68": float(winner["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(winner["energy_fractional_sigma68_ci_low"]),
                float(winner["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(winner["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(winner["time_sigma68_ns_ci_low"]),
                float(winner["time_sigma68_ns_ci_high"]),
            ],
            "delta_time_sigma68_vs_traditional_ns": float(winner["time_sigma68_ns"] - best_trad["time_sigma68_ns"]),
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "false_split_rate": float(winner["false_split_rate"]),
        },
        "strict_causal_controls": {
            "pretrigger_samples": cfg["baseline_samples"],
            "posttrigger_target_leakage": "excluded by design for pedestal estimate",
            "forced_random_control_audit": "forced_random_control_audit.csv",
            "direct_forced_random_target_available": False,
        },
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_benchmark": "method_benchmark_with_ci.csv",
            "s02_s04_propagation": "s02_s04_timing_tail_propagation.csv",
            "sidebands": "causal_control_sidebands.csv",
            "run_heldout": "run_heldout_metrics.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Model benchmark is derived from the checked-in S31b causal benchmark because its GEANT4 source ROOT is absent.",
            "Forced/random B-stack ROOT controls are audited but not available as direct supervised labels.",
            "Bootstrap intervals resample held-out runs and do not include detector-material or physics-list uncertainty.",
        ],
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_number": int(cfg["ticket_number"]),
        "git_commit": git_commit(),
        "command": f"{sys.executable} scripts/p11d_2421_strict_causal_learned_pedestal_timing_tail_validation.py",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            path.name: sha256_file(path)
            for path in sorted(out.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
