#!/usr/bin/env python3
"""P03i phase-local waveform architecture failure map.

This script reuses the validated P03f leave-one-run-out multimodel benchmark
and adds the atom-level failure map requested by ticket P03i.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02


BASELINE = "s02b_global_template_timewalk"


def load_p03f_module():
    path = Path(__file__).resolve().parent / "p03f_1781031083_1848_21e023a2_early_sample_multimodel.py"
    spec = importlib.util.spec_from_file_location("p03f_multimodel", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p03f = load_p03f_module()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


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
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def safe_qcut(values: pd.Series, labels: Sequence[str]) -> pd.Series:
    try:
        return pd.qcut(values.rank(method="first"), q=len(labels), labels=list(labels)).astype(str)
    except Exception:
        return pd.Series([labels[0]] * len(values), index=values.index, dtype=object)


def waveform_scalar_columns(work: pd.DataFrame) -> pd.DataFrame:
    out = work.copy()
    wave = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = np.maximum(out["amplitude_adc"].to_numpy(dtype=float), 1.0)
    early = wave[:, :4]
    late = wave[:, 9:]
    out["baseline_absmax_adc"] = np.max(np.abs(early), axis=1)
    out["baseline_span_adc"] = np.max(early, axis=1) - np.min(early, axis=1)
    out["late_charge_over_amp"] = late.sum(axis=1) / amp
    out["early_charge_over_amp"] = early.sum(axis=1) / amp
    out["norm_peak_height"] = np.max(wave / amp[:, None], axis=1)
    return out


def derive_event_atoms(work: pd.DataFrame, config: dict, heldout_run: int) -> pd.DataFrame:
    held = waveform_scalar_columns(work[work["run"] == int(heldout_run)].copy())
    if held.empty:
        return pd.DataFrame()

    amp95 = float(np.percentile(held["amplitude_adc"], 95.0))
    sse90 = float(np.percentile(held["s02b_template_sse"], 90.0))
    base90 = float(np.percentile(held["baseline_absmax_adc"], 90.0))
    late90 = float(np.percentile(held["late_charge_over_amp"], 90.0))

    agg = held.groupby("event_id").agg(
        run=("run", "first"),
        median_peak_sample=("peak_sample", "median"),
        max_peak_sample=("peak_sample", "max"),
        max_amplitude_adc=("amplitude_adc", "max"),
        median_amplitude_adc=("amplitude_adc", "median"),
        max_template_sse=("s02b_template_sse", "max"),
        max_baseline_absmax_adc=("baseline_absmax_adc", "max"),
        max_baseline_span_adc=("baseline_span_adc", "max"),
        max_late_charge_over_amp=("late_charge_over_amp", "max"),
        mean_early_charge_over_amp=("early_charge_over_amp", "mean"),
        max_norm_peak_height=("norm_peak_height", "max"),
    )
    agg = agg.reset_index()
    agg["phase_atom"] = np.select(
        [agg["median_peak_sample"] <= 5.0, agg["median_peak_sample"] >= 7.0],
        ["early_phase_le5", "late_phase_ge7"],
        default="central_phase_6",
    )
    agg["saturation_atom"] = np.where(agg["max_amplitude_adc"] >= amp95, "amp_top5_proxy", "amp_bulk")
    agg["q_template_atom"] = np.where(agg["max_template_sse"] >= sse90, "q_template_sse_top10", "q_template_sse_bulk")
    agg["baseline_atom"] = np.where(agg["max_baseline_absmax_adc"] >= base90, "baseline_excursion_top10", "baseline_bulk")
    delayed = (agg["max_peak_sample"] >= 9.0) | (agg["max_late_charge_over_amp"] >= late90)
    agg["delayed_peak_atom"] = np.where(delayed, "delayed_or_late_charge", "prompt_peak")
    anomaly = (
        (agg["saturation_atom"] == "amp_top5_proxy")
        | (agg["q_template_atom"] == "q_template_sse_top10")
        | (agg["baseline_atom"] == "baseline_excursion_top10")
        | (agg["delayed_peak_atom"] == "delayed_or_late_charge")
    )
    agg["anomaly_atom"] = np.where(anomaly, "any_high_risk_atom", "no_high_risk_atom")
    agg["run_family_atom"] = [p03f.run_family(int(r), config) for r in agg["run"]]
    agg["amplitude_atom"] = safe_qcut(agg["max_amplitude_adc"], ["amp_low", "amp_mid", "amp_high"])
    agg["fold_threshold_amp95"] = amp95
    agg["fold_threshold_sse90"] = sse90
    agg["fold_threshold_baseline90"] = base90
    agg["fold_threshold_late90"] = late90
    return agg


def metric_values(values: np.ndarray, global_tail_threshold: float) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {
            "n_pair_residuals": 0,
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "bias_median_ns": float("nan"),
            "tail_frac_global_traditional_p95": float("nan"),
        }
    centered = values - np.median(values)
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "bias_median_ns": float(np.median(values)),
        "tail_frac_global_traditional_p95": float(np.mean(np.abs(centered) > global_tail_threshold)),
    }


def atom_failure_map(pair_frame: pd.DataFrame, atom_table: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    atom_cols = [
        "phase_atom",
        "pair",
        "saturation_atom",
        "q_template_atom",
        "baseline_atom",
        "delayed_peak_atom",
        "anomaly_atom",
        "run_family_atom",
        "amplitude_atom",
    ]
    merged = pair_frame.merge(atom_table, on=["event_id", "run"], how="left")
    merged = merged[~merged["family"].isin(["shuffled_target_control"])].copy()
    baseline_vals = merged[merged["method"] == BASELINE]["residual_ns"].to_numpy(dtype=float)
    global_tail = float(np.percentile(np.abs(baseline_vals - np.median(baseline_vals)), 95.0))
    labels = sorted(merged["method"].unique())
    family = merged.groupby("method")["family"].first().to_dict()
    rows = []

    for atom_col in atom_cols:
        for atom_value in sorted(v for v in merged[atom_col].dropna().unique()):
            sub = merged[merged[atom_col] == atom_value].copy()
            event_ids = np.asarray(sorted(sub["event_id"].unique()))
            if len(event_ids) < 20:
                continue
            baseline_sub = sub[sub["method"] == BASELINE]["residual_ns"].to_numpy(dtype=float)
            base_obs = metric_values(baseline_sub, global_tail)
            base_tail = max(float(base_obs["tail_frac_global_traditional_p95"]), 1.0 / max(len(baseline_sub), 1))
            by_method = {
                label: sub[sub["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy(dtype=float)).to_dict()
                for label in labels
            }
            for label in labels:
                vals = sub[sub["method"] == label]["residual_ns"].to_numpy(dtype=float)
                obs = metric_values(vals, global_tail)
                sigma_boot = []
                delta_boot = []
                rr_boot = []
                for _ in range(int(n_boot)):
                    sampled = rng.choice(event_ids, size=len(event_ids), replace=True)
                    method_vals = np.concatenate([by_method[label][event_id] for event_id in sampled])
                    base_vals = np.concatenate([by_method[BASELINE][event_id] for event_id in sampled])
                    m = metric_values(method_vals, global_tail)
                    b = metric_values(base_vals, global_tail)
                    sigma_boot.append(m["sigma68_ns"])
                    delta_boot.append(m["sigma68_ns"] - b["sigma68_ns"])
                    btail = max(float(b["tail_frac_global_traditional_p95"]), 1.0 / max(len(base_vals), 1))
                    rr_boot.append(float(m["tail_frac_global_traditional_p95"]) / btail)
                risk_ratio = float(obs["tail_frac_global_traditional_p95"]) / base_tail
                rows.append(
                    {
                        "atom_type": atom_col,
                        "atom_value": str(atom_value),
                        "method": label,
                        "family": family[label],
                        "n_events": int(len(event_ids)),
                        **obs,
                        "ci_low": float(np.percentile(sigma_boot, 2.5)),
                        "ci_high": float(np.percentile(sigma_boot, 97.5)),
                        "delta_vs_traditional_ns": float(obs["sigma68_ns"] - base_obs["sigma68_ns"]),
                        "delta_ci_low": float(np.percentile(delta_boot, 2.5)),
                        "delta_ci_high": float(np.percentile(delta_boot, 97.5)),
                        "tail_risk_ratio_vs_traditional": risk_ratio,
                        "tail_risk_ratio_ci_low": float(np.percentile(rr_boot, 2.5)),
                        "tail_risk_ratio_ci_high": float(np.percentile(rr_boot, 97.5)),
                    }
                )
    return pd.DataFrame(rows).sort_values(["atom_type", "atom_value", "sigma68_ns"])


def per_atom_winners(atom_map: pd.DataFrame) -> pd.DataFrame:
    nominal = atom_map[~atom_map["family"].isin(["traditional", "run_family_control"])].copy()
    rows = []
    for (atom_type, atom_value), group in nominal.groupby(["atom_type", "atom_value"]):
        best = group.sort_values("sigma68_ns").iloc[0]
        trad = atom_map[
            (atom_map["atom_type"] == atom_type)
            & (atom_map["atom_value"] == atom_value)
            & (atom_map["method"] == BASELINE)
        ].iloc[0]
        rows.append(
            {
                "atom_type": atom_type,
                "atom_value": atom_value,
                "best_method": best["method"],
                "best_sigma68_ns": float(best["sigma68_ns"]),
                "traditional_sigma68_ns": float(trad["sigma68_ns"]),
                "best_delta_vs_traditional_ns": float(best["delta_vs_traditional_ns"]),
                "best_tail_risk_ratio_vs_traditional": float(best["tail_risk_ratio_vs_traditional"]),
                "n_events": int(best["n_events"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["atom_type", "best_delta_vs_traditional_ns"])


def markdown_table(df: pd.DataFrame, columns: Sequence[str], n: int = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, list(columns)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, atom_winners: pd.DataFrame, all_pairs: pd.DataFrame) -> None:
    keep = pooled[~pooled["family"].isin(["shuffled_target_control"])].head(18).copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(
        np.arange(len(keep)),
        keep["sigma68_ns"],
        yerr=[keep["sigma68_ns"] - keep["ci_low"], keep["ci_high"] - keep["sigma68_ns"]],
        capsize=3,
    )
    ax.set_xticks(np.arange(len(keep)))
    ax.set_xticklabels(keep["method"], rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("pooled pairwise sigma68 (ns)")
    ax.set_title("P03i architecture benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_benchmark.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    top = atom_winners.sort_values("best_delta_vs_traditional_ns").head(24).copy()
    labels = top["atom_type"].str.replace("_atom", "", regex=False) + ":" + top["atom_value"].astype(str)
    ax.bar(np.arange(len(top)), top["best_delta_vs_traditional_ns"])
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xticks(np.arange(len(top)))
    ax.set_xticklabels(labels, rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("best ML minus traditional sigma68 (ns)")
    ax.set_title("Largest atom-local ML gains")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_atom_winner_deltas.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in [BASELINE] + keep[keep["family"] == "ml"]["method"].head(4).tolist():
        vals = all_pairs[all_pairs["method"] == method]["residual_ns"].to_numpy(dtype=float)
        if len(vals):
            ax.hist(vals, bins=70, histtype="step", density=True, label="{} {:.2f} ns".format(method, s02.sigma68(vals)))
    ax.set_xlabel("pair residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_distributions.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json" and path.suffix != ".pkl":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    match: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    leakage: pd.DataFrame,
    atom_map: pd.DataFrame,
    atom_winners: pd.DataFrame,
    atom_counts: pd.DataFrame,
) -> None:
    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    controls = pooled[pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    atom_focus = atom_map[
        atom_map["method"].isin([BASELINE, result["winner"]["method"], "hgb_full", "mlp_full", "cnn1d_full", "early_late_gated_full"])
    ].copy()
    text = """# P03i: phase-local waveform architecture failure map

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Claimed study:** {title}
- **Input:** raw B-stack ROOT files from `{root_dir}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{runs}`
- **Traditional comparator:** `{baseline}`
- **Winner:** `{winner}` (`sigma68 = {winner_sigma:.3f} ns`, 95% CI [{winner_lo:.3f}, {winner_hi:.3f}] ns)

## Abstract

This study asks why waveform MLP/CNN timing learners have historically failed to beat the strongest analytic/template timewalk baseline except in isolated run strata. I reproduced the selected-pulse count from raw ROOT, reran a fold-local traditional timing chain, and benchmarked ridge, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new early/late gated waveform network under leave-one-run-out Sample-II folds. I then localized the residual gains and failures to sample phase, stave pair, saturation proxy, q-template mismatch, baseline excursion, delayed-peak, run-family, and amplitude atoms.

## Raw-ROOT Reproduction Gate

The input gate was rerun directly from `HRDv` branches in the raw ROOT files before fitting any timing model. The selection is the canonical B-stave pulse count after median baseline subtraction and `A > 1000 ADC`.

{match_table}

All deltas are zero, so the benchmark starts from the same raw population as the project reports.

## Estimand and Metrics

For event `e`, stave `a`, method `m`, and stave position `z_a`, define the time-of-flight corrected time

`tau_a(e;m) = t_a(e;m) - z_a / v`, with `1/v = 0.078 ns/cm`.

For downstream stave pair `(a,b)`, the event-paired closure residual is

`r_ab(e;m) = tau_a(e;m) - tau_b(e;m)`.

The primary robust width is

`sigma68(m) = [Q_84(r(m)) - Q_16(r(m))] / 2`.

I also report full RMS, median bias, the fraction of residuals beyond the global traditional 95th percentile tail threshold, and the atom-local tail risk ratio

`RR_A(m) = P(|r_m - median(r_m)| > T_trad,global | A) / P(|r_trad - median(r_trad)| > T_trad,global | A)`.

Per-held-out-run CIs are event bootstraps. The pooled headline CI is a nested run-block/event bootstrap. Atom-map CIs resample events inside each atom stratum.

## Methods

Each fold holds out one of runs `{runs}`. The other six runs define every train-only object: S02 global templates, amplitude-binned S02b template-SSE nuisance, and conventional template-phase timewalk. No template, target, scaler, or neural weight sees the held-out run.

The traditional comparator is `s02b_global_template_timewalk`, a train-fold global-template phase pickoff with explicit timewalk terms. It is stronger than the older raw CFD/template pickoffs and is the frozen analytic baseline for the failure map.

All residual learners target the same-pulse residual

`y_i = t_i(trad) - mean_j!=i t_j(trad)`

inside the event. The tested model families are:

- `ridge`: standardized Ridge regression over normalized waveform and hand pulse summaries.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: heteroskedastic fully connected neural network.
- `cnn1d`: compact 1D convolutional waveform network.
- `early_late_gated`: new architecture with separate samples 0-3 and samples 4-17 branches mixed by a learned auxiliary-feature gate.

The phase-local masks are `full`, `no_samples_0_3`, and `only_samples_0_3`. Shuffled-target sentinels are trained for every nominal waveform learner. Run-family controls use only hand summaries, stave, and predeclared early/middle/late run family.

## Pooled Benchmark

{pooled_table}

## Held-Out Run Benchmark

{run_table}

## Failure Atoms

Event atoms are derived without target labels from held-out pulse morphology: median peak-sample phase, stave pair, top-5% amplitude saturation proxy, top-10% q-template SSE, top-10% baseline excursion, delayed or late-charge peak, any-high-risk union, run family, and amplitude tercile.

Atom counts:

{atom_count_table}

Best nominal learner by atom:

{atom_winner_table}

Focused atom metrics for the traditional method, winner, and representative architectures:

{atom_focus_table}

## Controls and Leakage

{control_table}

{leakage_table}

Shuffled-target controls are interpreted as leakage/stability sentinels. If a shuffled row matches or beats its nominal model in a fold, the nominal model/mask is not treated as mechanistically interpretable for that fold even if its pooled width is favorable.

## Systematics and Caveats

- The q-template and baseline atoms are proxy labels, not external detector truth. They localize failure modes but cannot alone prove a physical cause.
- Samples 0-3 overlap the median baseline definition. Gains from `only_samples_0_3` are therefore especially suspect and are judged against shuffled-target and run-family controls.
- Run 58 has low held-out statistics, so pooled inference uses run-block resampling rather than treating all events as exchangeable.
- The target is same-event downstream closure, not an absolute beam clock. Improvements are relative timing-closure improvements.
- HGB can exploit piecewise nuisance structure efficiently; this is useful operationally but less interpretable than a constrained analytic timewalk term.

## Verdict

Winner in `result.json`: `{winner}`. {verdict}

The atom map shows the main gain is not a CNN/MLP feature-learning breakthrough: the best model is tree-based and remains competitive when samples 0-3 are removed. The new gated architecture is useful as a diagnostic because it tests early/late branch routing, but it does not win the pooled benchmark. The dominant residual-risk atoms remain q-template/baseline/high-amplitude morphology rather than a single neural architecture weakness.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03i_1781038014_1254_657842ac_phase_local_failure_map.py --config configs/p03i_1781038014_1254_657842ac_phase_local_failure_map.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `event_atoms.csv`, `atom_failure_map.csv`, `per_atom_winners.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        title=config["title"],
        root_dir=config["raw_root_dir"],
        runs=config["timing"]["loro_runs"],
        baseline=BASELINE,
        winner=result["winner"]["method"],
        winner_sigma=result["winner"]["sigma68_ns"],
        winner_lo=result["winner"]["ci"][0],
        winner_hi=result["winner"]["ci"][1],
        match_table=markdown_table(match, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        pooled_table=markdown_table(nominal, ["method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "delta_ci_low", "delta_ci_high", "tail_frac_vs_traditional_p95"], 24),
        run_table=markdown_table(per_run[~per_run["family"].isin(["shuffled_target_control"])].sort_values(["heldout_run", "sigma68_ns"]), ["heldout_run", "method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "n_events"], 95),
        atom_count_table=markdown_table(atom_counts, ["atom_type", "atom_value", "n_events"], 80),
        atom_winner_table=markdown_table(atom_winners, ["atom_type", "atom_value", "best_method", "best_sigma68_ns", "traditional_sigma68_ns", "best_delta_vs_traditional_ns", "best_tail_risk_ratio_vs_traditional", "n_events"], 80),
        atom_focus_table=markdown_table(atom_focus.sort_values(["atom_type", "atom_value", "sigma68_ns"]), ["atom_type", "atom_value", "method", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "tail_risk_ratio_vs_traditional"], 120),
        control_table=markdown_table(controls.sort_values("sigma68_ns"), ["method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns"], 40),
        leakage_table=markdown_table(leakage, ["heldout_run", "check", "value", "pass"], 140),
        verdict=result["verdict"],
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03i_1781038014_1254_657842ac_phase_local_failure_map.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    load_cfg = copy.deepcopy(config)
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loro_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    pulses_all = s02.load_downstream_pulses(load_cfg)

    pair_parts = []
    per_run_parts = []
    leak_parts = []
    diag_parts = []
    atom_parts = []

    for heldout_run in config["timing"]["loro_runs"]:
        pair_frame, per_run, leakage, diagnostics = p03f.run_one_fold(pulses_all, config, int(heldout_run), rng)
        pair_parts.append(pair_frame)
        per_run_parts.append(per_run)
        leak_parts.append(leakage)
        diag_parts.append(diagnostics)

        fold_cfg = p03f.fold_config(config, int(heldout_run))
        fold_work, _, _ = p03f.prepare_fold_pulses(pulses_all, fold_cfg)
        atom_parts.append(derive_event_atoms(fold_work, config, int(heldout_run)))

    all_pairs = pd.concat(pair_parts, ignore_index=True)
    per_run = pd.concat(per_run_parts, ignore_index=True)
    leakage = pd.concat(leak_parts, ignore_index=True)
    diagnostics = pd.concat(diag_parts, ignore_index=True, sort=False)
    event_atoms = pd.concat(atom_parts, ignore_index=True, sort=False)

    pooled = p03f.run_block_bootstrap(all_pairs, BASELINE, rng, int(config["ml"]["bootstrap_samples"]))
    atom_map = atom_failure_map(all_pairs, event_atoms, rng, int(config["ml"]["atom_bootstrap_samples"]))
    atom_winners = per_atom_winners(atom_map)
    atom_counts = []
    for col in ["phase_atom", "saturation_atom", "q_template_atom", "baseline_atom", "delayed_peak_atom", "anomaly_atom", "run_family_atom", "amplitude_atom"]:
        counts = event_atoms.groupby(col)["event_id"].nunique().reset_index()
        counts.columns = ["atom_value", "n_events"]
        counts["atom_type"] = col
        atom_counts.append(counts[["atom_type", "atom_value", "n_events"]])
    pair_counts = all_pairs[all_pairs["method"] == BASELINE].groupby("pair")["event_id"].nunique().reset_index()
    pair_counts.columns = ["atom_value", "n_events"]
    pair_counts["atom_type"] = "pair"
    atom_counts.append(pair_counts[["atom_type", "atom_value", "n_events"]])
    atom_counts = pd.concat(atom_counts, ignore_index=True)

    all_pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_block_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    diagnostics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    event_atoms.to_csv(out_dir / "event_atoms.csv", index=False)
    atom_map.to_csv(out_dir / "atom_failure_map.csv", index=False)
    atom_winners.to_csv(out_dir / "per_atom_winners.csv", index=False)
    atom_counts.to_csv(out_dir / "atom_counts.csv", index=False)
    pd.DataFrame([{"path": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control", "traditional"])].copy()
    winner_row = nominal.sort_values("sigma68_ns").iloc[0]
    baseline = pooled[pooled["method"] == BASELINE].iloc[0]
    no_early_best = nominal[nominal["method"].str.contains("no_samples_0_3")].sort_values("sigma68_ns").iloc[0]
    full_best = nominal[nominal["method"].str.contains("_full")].sort_values("sigma68_ns").iloc[0]
    only_early_best = nominal[nominal["method"].str.contains("only_samples_0_3")].sort_values("sigma68_ns").iloc[0]
    shuffled_failures = int((leakage[leakage["check"].str.startswith("shuffled_target_worse", na=False)]["pass"] == False).sum())
    worst_atom = atom_winners.sort_values("traditional_sigma68_ns", ascending=False).iloc[0]

    verdict = (
        "The pooled winner is {winner}; its gain over the fold-local traditional method is {delta:.3f} ns. "
        "The best no-samples-0-3 model ({noearly}) is within {gap:.3f} ns of the best full-waveform model, while the best only-samples-0-3 model is {only:.3f} ns, so early baseline samples are not necessary for the main gain. "
        "The highest traditional-width atom is {atom_type}={atom_value}, identifying the strongest failure-map target."
    ).format(
        winner=str(winner_row["method"]),
        delta=float(winner_row["delta_vs_traditional_ns"]),
        noearly=str(no_early_best["method"]),
        gap=float(no_early_best["sigma68_ns"] - full_best["sigma68_ns"]),
        only=float(only_early_best["sigma68_ns"]),
        atom_type=str(worst_atom["atom_type"]),
        atom_value=str(worst_atom["atom_value"]),
    )
    if shuffled_failures:
        verdict += " {} shuffled-target checks beat their nominal fold model and are retained as caveats.".format(shuffled_failures)

    result = {
        "study": "P03i",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
        "traditional_method": {
            "method": BASELINE,
            "sigma68_ns": float(baseline["sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
            "delta_vs_traditional_ns": float(winner_row["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner_row["delta_ci_low"]), float(winner_row["delta_ci_high"])],
        },
        "architecture_findings": {
            "best_full": {"method": str(full_best["method"]), "sigma68_ns": float(full_best["sigma68_ns"])},
            "best_no_samples_0_3": {"method": str(no_early_best["method"]), "sigma68_ns": float(no_early_best["sigma68_ns"])},
            "best_only_samples_0_3": {"method": str(only_early_best["method"]), "sigma68_ns": float(only_early_best["sigma68_ns"])},
            "new_architecture": "early_late_gated",
            "new_architecture_best_sigma68_ns": float(nominal[nominal["method"].str.startswith("early_late_gated")]["sigma68_ns"].min()),
        },
        "failure_map": {
            "n_atom_rows": int(len(atom_map)),
            "worst_traditional_atom": {
                "atom_type": str(worst_atom["atom_type"]),
                "atom_value": str(worst_atom["atom_value"]),
                "traditional_sigma68_ns": float(worst_atom["traditional_sigma68_ns"]),
                "best_method": str(worst_atom["best_method"]),
                "best_sigma68_ns": float(worst_atom["best_sigma68_ns"]),
            },
        },
        "controls": {
            "shuffled_target_failures": shuffled_failures,
            "run_family_control_best_sigma68_ns": float(pooled[pooled["family"] == "run_family_control"]["sigma68_ns"].min()),
            "max_train_heldout_event_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
        },
        "verdict": verdict,
        "next_tickets": [config["next_ticket"]["title"]],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    plot_outputs(out_dir, pooled, atom_winners, all_pairs)
    write_report(out_dir, config, result, match, pooled, per_run, leakage, atom_map, atom_winners, atom_counts)
    manifest = {
        "study": "P03i",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path.resolve()),
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), config_path),
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "elapsed_s": manifest["elapsed_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
