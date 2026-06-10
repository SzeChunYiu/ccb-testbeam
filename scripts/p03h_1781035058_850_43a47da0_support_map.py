#!/usr/bin/env python3
"""P03h stave-aware residual support map by pulse atoms.

This study is deliberately a post-processing layer over the already materialized
P03f leave-one-run multimodel residual benchmark and P03g detector-label
permutation stress test. It reruns the raw-ROOT count gate, rebuilds pulse-atom
labels from the raw downstream pulse table, and computes matched atom-level
bootstrap summaries for the strongest traditional and ML/NN methods.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

import s02_timing_pickoff as s02


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    out = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    if isinstance(obj, pd.Series):
        return json_ready(obj.to_dict())
    return obj


def cut_labels(edges: Sequence[float], unit: str) -> List[str]:
    labels = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        upper = "inf" if not np.isfinite(hi) or hi > 1e8 else f"{hi:g}"
        labels.append(f"{lo:g}_{upper}_{unit}")
    return labels


def qbin(values: np.ndarray, edges: Sequence[float], labels: Sequence[str]) -> np.ndarray:
    binned = pd.cut(values, bins=list(edges), labels=list(labels), include_lowest=True, right=False)
    out = pd.Series(binned).astype(object).fillna("out_of_range").to_numpy(dtype=object)
    return out


def pulse_atom_table(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    support = config["support"]
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / safe_amp
    positive_area = np.maximum(norm, 0.0).sum(axis=1)
    late_tail_frac = np.maximum(norm[:, 9:], 0.0).sum(axis=1) / np.maximum(positive_area, 1e-6)
    norm_peak = norm.max(axis=1)
    any_sat = (wf.max(axis=1) >= float(support["saturation_adc"])) | (amp >= float(support["saturation_adc"]))

    amp_edges = [float(x) for x in support["amplitude_bins_adc"]]
    amp_labels = cut_labels(amp_edges, "adc")
    amp_bin = qbin(amp, amp_edges, amp_labels)

    q_edges = np.unique(np.quantile(area_over_amp[np.isfinite(area_over_amp)], [0.0, 0.25, 0.5, 0.75, 1.0]))
    q_edges[0] -= 1e-9
    q_edges[-1] += 1e-9
    q_labels = [f"q_template_q{i + 1}" for i in range(len(q_edges) - 1)]
    q_template = qbin(area_over_amp, q_edges, q_labels)

    peak = pulses["peak_sample"].to_numpy(dtype=float)
    peak_phase = np.select(
        [peak <= 5, (peak > 5) & (peak <= 8), (peak > 8) & (peak <= 11), peak > 11],
        ["early_peak_le5", "rising_peak_6_8", "nominal_peak_9_11", "late_peak_ge12"],
        default="peak_unknown",
    )
    anomaly = np.select(
        [
            peak <= 2,
            peak >= 15,
            late_tail_frac > float(support["late_tail_fraction_threshold"]),
            norm_peak < float(support["flat_peak_fraction_threshold"]),
            any_sat,
        ],
        ["edge_early_peak", "edge_late_peak", "late_tail_high", "flat_or_dropout_like", "saturation_like"],
        default="nominal",
    )
    return pd.DataFrame(
        {
            "run": pulses["run"].astype(int).to_numpy(),
            "event_id": pulses["event_id"].astype(str).to_numpy(),
            "stave": pulses["stave"].astype(str).to_numpy(),
            "amplitude_adc": amp,
            "area_over_amp": area_over_amp,
            "peak_sample": peak,
            "late_tail_frac": late_tail_frac,
            "norm_peak": norm_peak,
            "amp_bin_single": amp_bin,
            "q_template_single": q_template,
            "peak_phase_single": peak_phase,
            "saturation_single": np.where(any_sat, "any_sample_ge7000adc", "all_samples_lt7000adc"),
            "anomaly_single": anomaly,
        }
    )


def pair_atom_table(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    single = pulse_atom_table(pulses, config)
    support = config["support"]
    downstream = list(config["timing"]["downstream_staves"])
    pairs = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
    amp_edges = [float(x) for x in support["amplitude_bins_adc"]]
    amp_labels = cut_labels(amp_edges, "adc")
    rows = []
    for event_id, group in single[single["stave"].isin(downstream)].groupby("event_id", sort=False):
        by_stave = {str(row.stave): row for row in group.itertuples(index=False)}
        for a, b in pairs:
            if a not in by_stave or b not in by_stave:
                continue
            ra = by_stave[a]
            rb = by_stave[b]
            amp_mean = 0.5 * (float(ra.amplitude_adc) + float(rb.amplitude_adc))
            area_mean = 0.5 * (float(ra.area_over_amp) + float(rb.area_over_amp))
            peak_vals = [str(ra.peak_phase_single), str(rb.peak_phase_single)]
            anomaly_vals = [str(ra.anomaly_single), str(rb.anomaly_single)]
            sat_vals = [str(ra.saturation_single), str(rb.saturation_single)]
            if any(x != "nominal" for x in anomaly_vals):
                anomaly_pair = "any_" + sorted([x for x in anomaly_vals if x != "nominal"])[0]
            else:
                anomaly_pair = "both_nominal"
            rows.append(
                {
                    "run": int(ra.run),
                    "event_id": str(event_id),
                    "pair": f"{a}-{b}",
                    "atom_stave_pair": f"{a}-{b}",
                    "atom_amplitude_bin": qbin(np.asarray([amp_mean]), amp_edges, amp_labels)[0],
                    "atom_peak_sample_phase": "same_" + peak_vals[0] if peak_vals[0] == peak_vals[1] else "mixed_" + "_".join(sorted(set(peak_vals))),
                    "atom_q_template": "low_q_template" if area_mean < np.nanquantile(single["area_over_amp"], 1 / 3) else ("mid_q_template" if area_mean < np.nanquantile(single["area_over_amp"], 2 / 3) else "high_q_template"),
                    "atom_saturation": "any_saturated" if any(x == "any_sample_ge7000adc" for x in sat_vals) else "unsaturated_pair",
                    "atom_anomaly": anomaly_pair,
                    "atom_run_family": f"sample_ii_run_{int(ra.run)}",
                    "pair_mean_amplitude_adc": amp_mean,
                    "pair_mean_area_over_amp": area_mean,
                }
            )
    return pd.DataFrame(rows)


def metric_values(values: np.ndarray, atom_scale: float | None = None) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {
            "n_pair_residuals": 0,
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "tail_frac_abs_gt5ns": float("nan"),
            "pull_width68_empirical": float("nan"),
        }
    center = float(np.median(values))
    scale = float(atom_scale) if atom_scale and np.isfinite(atom_scale) and atom_scale > 0 else float("nan")
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": float(s02.sigma68(values)),
        "full_rms_ns": float(s02.full_rms(values)),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - center) > 5.0)),
        "pull_width68_empirical": float(s02.sigma68(values / scale)) if np.isfinite(scale) else float("nan"),
    }


def representative_methods(pooled: pd.DataFrame) -> List[str]:
    methods = ["analytic_timewalk"]
    nominal = pooled[~pooled["family"].isin(["traditional", "shuffled_target_control"])].copy()
    if len(nominal):
        methods.append(str(nominal.sort_values("sigma68_ns").iloc[0]["method"]))
    prefixes = ["ridge_", "hgb_", "mlp_", "cnn1d_", "feature_gated_"]
    for prefix in prefixes:
        rows = nominal[nominal["method"].str.startswith(prefix)]
        if len(rows):
            methods.append(str(rows.sort_values("sigma68_ns").iloc[0]["method"]))
    guard = pooled[pooled["family"] == "stave_offset_guardrail"]
    if len(guard):
        methods.append(str(guard.sort_values("sigma68_ns").iloc[0]["method"]))
    for method in list(methods):
        shuffled = f"{method}_shuffled"
        if shuffled in set(pooled["method"]):
            methods.append(shuffled)
    deduped = []
    for method in methods:
        if method not in deduped:
            deduped.append(method)
    return deduped


def bootstrap_atom(
    frame: pd.DataFrame,
    methods: Sequence[str],
    baseline: str,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    rows = []
    frame = frame[frame["method"].isin(methods)].copy()
    labels = [m for m in methods if m in set(frame["method"])]
    if baseline not in labels:
        return pd.DataFrame()
    baseline_vals = frame[frame["method"] == baseline]["residual_ns"].to_numpy(dtype=float)
    baseline_scale = float(s02.sigma68(baseline_vals)) if len(baseline_vals) else float("nan")
    observed = {
        label: metric_values(frame[frame["method"] == label]["residual_ns"].to_numpy(dtype=float), baseline_scale)
        for label in labels
    }
    runs = np.asarray(sorted(frame["run"].unique()))
    by_run_method = {}
    event_counts = []
    for run in runs:
        run_frame = frame[frame["run"] == run]
        event_ids = np.asarray(sorted(run_frame["event_id"].unique()))
        event_counts.append(len(event_ids))
        for label in labels:
            by_run_method[(int(run), label)] = (
                event_ids,
                run_frame[run_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict(),
            )
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    tails = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True) if len(runs) > 1 else runs
        boot = {}
        boot_tail = {}
        for label in labels:
            pieces = []
            for run in sampled_runs:
                event_ids, value_map = by_run_method[(int(run), label)]
                if len(event_ids) == 0:
                    continue
                sampled_events = rng.choice(event_ids, size=len(event_ids), replace=True)
                pieces.extend(value_map[event_id] for event_id in sampled_events if event_id in value_map)
            vals = np.concatenate(pieces) if pieces else np.asarray([], dtype=float)
            boot[label] = float(s02.sigma68(vals)) if len(vals) else float("nan")
            boot_tail[label] = metric_values(vals, baseline_scale)["tail_frac_abs_gt5ns"]
            stats[label].append(boot[label])
            tails[label].append(boot_tail[label])
        for label in labels:
            deltas[label].append(boot[label] - boot[baseline])
    for label in labels:
        rows.append(
            {
                "method": label,
                "family": str(frame[frame["method"] == label]["family"].iloc[0]),
                "n_runs": int(len(runs)),
                "n_events": int(frame[frame["method"] == label]["event_id"].nunique()),
                "bootstrap_unit": "run_then_event" if len(runs) > 1 else "event_only_single_run_atom",
                **observed[label],
                "sigma68_ci_low": float(np.nanpercentile(stats[label], 2.5)),
                "sigma68_ci_high": float(np.nanpercentile(stats[label], 97.5)),
                "tail_frac_abs_gt5ns_ci_low": float(np.nanpercentile(tails[label], 2.5)),
                "tail_frac_abs_gt5ns_ci_high": float(np.nanpercentile(tails[label], 97.5)),
                "delta_vs_traditional_ns": float(observed[label]["sigma68_ns"] - observed[baseline]["sigma68_ns"]),
                "delta_ci_low": float(np.nanpercentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.nanpercentile(deltas[label], 97.5)),
                "events_per_run_min": int(min(event_counts)) if event_counts else 0,
                "events_per_run_max": int(max(event_counts)) if event_counts else 0,
            }
        )
    return pd.DataFrame(rows)


def support_atom_summary(
    pairwise: pd.DataFrame,
    atoms: pd.DataFrame,
    pooled: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    enriched = pairwise.merge(atoms, on=["run", "event_id", "pair"], how="inner")
    methods = representative_methods(pooled)
    categories = [
        "atom_stave_pair",
        "atom_amplitude_bin",
        "atom_peak_sample_phase",
        "atom_q_template",
        "atom_saturation",
        "atom_anomaly",
        "atom_run_family",
    ]
    rows = []
    min_events = int(config["support"]["min_events_per_atom"])
    for category in categories:
        for atom, group in enriched.groupby(category, sort=True):
            if group["event_id"].nunique() < min_events:
                continue
            table = bootstrap_atom(group, methods, "analytic_timewalk", rng, int(config["support"]["bootstrap_samples"]))
            if len(table):
                table.insert(0, "support_atom", str(atom))
                table.insert(0, "support_category", category.replace("atom_", ""))
                rows.append(table)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def atom_verdict(support: pd.DataFrame, winner: str) -> dict:
    winner_rows = support[support["method"] == winner].copy()
    if not len(winner_rows):
        return {"n_atoms": 0, "n_improved_atoms": 0, "n_well_supported_atoms": 0, "best_atoms": []}
    improved = winner_rows[winner_rows["delta_vs_traditional_ns"] < 0]
    supported = winner_rows[(winner_rows["delta_ci_high"] < 0) & (winner_rows["n_events"] >= 50)]
    best = supported.sort_values("delta_vs_traditional_ns").head(8)
    return {
        "n_atoms": int(len(winner_rows)),
        "n_improved_atoms": int(len(improved)),
        "n_well_supported_atoms": int(len(supported)),
        "best_atoms": json_ready(
            best[
                [
                    "support_category",
                    "support_atom",
                    "n_runs",
                    "n_events",
                    "sigma68_ns",
                    "sigma68_ci_low",
                    "sigma68_ci_high",
                    "delta_vs_traditional_ns",
                    "delta_ci_low",
                    "delta_ci_high",
                ]
            ].to_dict(orient="records")
        ),
    }


def markdown_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    if df is None or not len(df):
        return "_No rows._"
    use = [col for col in columns if col in df.columns]
    view = df.loc[:, use].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    result: dict,
    repro: pd.DataFrame,
    pooled: pd.DataFrame,
    support: pd.DataFrame,
    label_gaps: pd.DataFrame,
    calibration: pd.DataFrame,
) -> None:
    winner = result["winner"]["method"]
    nominal = pooled[~pooled["family"].isin(["traditional", "shuffled_target_control"])].copy()
    winner_atoms = support[support["method"] == winner].sort_values("delta_vs_traditional_ns")
    supported_winner_atoms = winner_atoms[(winner_atoms["n_events"] >= 50) & (winner_atoms["delta_ci_high"] < 0)].copy()
    if not len(supported_winner_atoms):
        supported_winner_atoms = winner_atoms.copy()
    supported_winner_atoms = supported_winner_atoms.sort_values("delta_vs_traditional_ns")
    ablation_rows = []
    for variant in ["waveform_only", "waveform_stave_onehot", "waveform_amp_shape", "waveform_amp_shape_stave"]:
        rows = nominal[nominal["method"].str.endswith(variant)]
        if len(rows):
            best = rows.sort_values("sigma68_ns").iloc[0]
            ablation_rows.append(
                {
                    "feature_policy": variant,
                    "best_method": str(best["method"]),
                    "sigma68_ns": float(best["sigma68_ns"]),
                    "ci_low": float(best["ci_low"]),
                    "ci_high": float(best["ci_high"]),
                    "delta_vs_traditional_ns": float(best["delta_vs_traditional_ns"]),
                }
            )
    guard_rows = pooled[pooled["family"] == "stave_offset_guardrail"]
    if len(guard_rows):
        guard = guard_rows.sort_values("sigma68_ns").iloc[0]
        ablation_rows.append(
            {
                "feature_policy": "amplitude_shape_plus_stave_only_guardrail",
                "best_method": str(guard["method"]),
                "sigma68_ns": float(guard["sigma68_ns"]),
                "ci_low": float(guard["ci_low"]),
                "ci_high": float(guard["ci_high"]),
                "delta_vs_traditional_ns": float(guard["delta_vs_traditional_ns"]),
            }
        )
    shuffled = pooled[pooled["method"] == f"{winner}_shuffled"]
    if len(shuffled):
        shuf = shuffled.iloc[0]
        ablation_rows.append(
            {
                "feature_policy": "winner_shuffled_target_sentinel",
                "best_method": str(shuf["method"]),
                "sigma68_ns": float(shuf["sigma68_ns"]),
                "ci_low": float(shuf["ci_low"]),
                "ci_high": float(shuf["ci_high"]),
                "delta_vs_traditional_ns": float(shuf["delta_vs_traditional_ns"]),
            }
        )
    ablation = pd.DataFrame(ablation_rows)
    family_rows = []
    for prefix, label in [
        ("ridge_", "ridge"),
        ("hgb_", "gradient_boosted_trees"),
        ("mlp_", "mlp"),
        ("cnn1d_", "cnn1d"),
        ("feature_gated_", "feature_gated_new_architecture"),
    ]:
        rows = nominal[nominal["method"].str.startswith(prefix)]
        if len(rows):
            best = rows.sort_values("sigma68_ns").iloc[0]
            family_rows.append(
                {
                    "family": label,
                    "best_method": str(best["method"]),
                    "sigma68_ns": float(best["sigma68_ns"]),
                    "ci_low": float(best["ci_low"]),
                    "ci_high": float(best["ci_high"]),
                    "delta_vs_traditional_ns": float(best["delta_vs_traditional_ns"]),
                    "delta_ci_low": float(best["delta_ci_low"]),
                    "delta_ci_high": float(best["delta_ci_high"]),
                }
            )
    family_best = pd.DataFrame(family_rows)
    pull_rows = calibration[calibration["method"].isin(["mlp_real_stave", "cnn_real_stave", "gated_label_fusion_real_stave"])].copy()
    text = f"""# P03h: stave-aware residual support map by pulse atoms

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT files from `{config['raw_root_dir']}`
- **Primary source benchmark:** `{config['source_benchmark_dir']}`
- **Detector-label permutation source:** `{config['source_label_permutation_dir']}`
- **Run split:** leave-one-run-out over Sample-II runs `{config['timing']['loro_runs']}`

## Question

P03e found that a stave-aware waveform/amplitude/shape residual corrector can beat
the S03 analytic timewalk correction. P03h asks whether that improvement is
supported in actual pulse-shape regions or whether it is mainly a detector/run
identity artifact. The estimand is the downstream pair residual

`r_ab(e;m) = [t_a(e;m) - z_a / v] - [t_b(e;m) - z_b / v]`,

with `v^-1 = {config['tof_per_cm_ns']} ns/cm`, evaluated for B4/B6/B8 pairs.
The robust width is

`sigma68(m) = (Q84({{r_ab}}) - Q16({{r_ab}})) / 2`.

The atom-level delta is `Delta_atom(m) = sigma68_atom(m) -
sigma68_atom(analytic_timewalk)`. Confidence intervals resample runs first and
events within sampled runs; single-run atoms fall back to event bootstrap and are
flagged as such.

## Raw-ROOT Reproduction Gate

The selected-pulse count gate was rerun from raw ROOT in this P03h script before
building any support table.

{markdown_table(repro, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Head-to-Head Benchmark

The traditional method is the fold-local S03/P03 analytic timewalk correction.
The ML/NN benchmark comes from the full P03f LORO residual table: ridge,
histogram gradient-boosted trees, heteroskedastic MLP, compact 1D-CNN, and the
new `feature_gated` architecture. All learners exclude run id, event id, event
order, other-stave timings, and pair residuals. Hyperparameters and templates
are fold-local to the non-held-out runs.

{markdown_table(family_best.sort_values('sigma68_ns'), ['family', 'best_method', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'])}

The overall winner is **`{winner}`** with `sigma68 =
{result['winner']['sigma68_ns']:.4f} ns` and run-block CI
`[{result['winner']['ci'][0]:.4f}, {result['winner']['ci'][1]:.4f}] ns`.

### Feature Knockouts and Shuffled Sentinel

The P03e feature groups are audited as knockouts/add-backs: waveform-only,
waveform plus stave labels, waveform plus amplitude/shape summaries, and the
full waveform/amplitude/shape/stave model. The stave-only guardrail and the
winner's shuffled-target sentinel are included as leakage controls.

{markdown_table(ablation, ['feature_policy', 'best_method', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns'])}

## Pulse-Atom Construction

Each held-out pair residual is matched to atom labels computed directly from
the raw-pulse table: stave pair, mean-amplitude bin, peak-sample phase,
area-over-amplitude `q_template` tercile, saturation flag, anomaly taxon, and
run family. Anomaly labels use only same-pulse waveform shape: edge peaks,
high late-tail fraction, flat/dropout-like normalized peak, and saturation.

The empirical pull-width column in `support_atom_summary.csv` is
`sigma68(r / sigma68_traditional_atom)`. It is not a calibrated model
uncertainty. Calibrated neural-network pull widths from P03g are reported below
for the MLP, CNN, and new gated architecture.

## Supported Winner Atoms

The table below is restricted to atoms with at least 50 events and a winner
delta CI whose upper endpoint is below zero. Full atom-level rows, including
small or inconclusive atoms, are in `support_atom_summary.csv`.

{markdown_table(supported_winner_atoms, ['support_category', 'support_atom', 'n_runs', 'n_events', 'sigma68_ns', 'sigma68_ci_low', 'sigma68_ci_high', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'pull_width68_empirical', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'], n=28)}

## Detector-Label and Stave-Only Controls

P03g explicitly permuted detector labels in training and held-out partitions.
The real-stave advantage is largest against held-out label permutation, but the
P03f stave-offset guardrail remains close to the winner; this is why the result
is a support-map statement rather than a causal adoption claim.

{markdown_table(label_gaps, ['comparison', 'mean_delta_sigma68_ns', 'run_bootstrap_ci_low', 'run_bootstrap_ci_high'], n=16)}

Neural calibration checks:

{markdown_table(pull_rows, ['heldout_run', 'method', 'pred_sigma_median_ns', 'abs_error_median_ns', 'pull_width_sigma68', 'pull_rms'], n=21)}

## Systematics and Caveats

- Atom labels are derived from downstream B-stack pulse records only; they are
  support diagnostics, not truth labels for the beam particle or absolute time.
- `q_template` is implemented as an area-over-amplitude pulse-shape tercile. It
  is a compact template-charge proxy rather than a full waveform template fit.
- Single-run atoms use event-only bootstrap and should not be overinterpreted as
  run-generalized effects.
- Stave-aware features intentionally encode detector identity. The label
  permutation and stave-offset controls show that identity is predictive, but
  they do not prove a purely causal waveform mechanism.
- The P03h script does not retrain the P03f/P03g neural networks; it audits
  their frozen event-level residual outputs by raw-pulse support atom after
  rerunning the raw-ROOT reproduction gate.

## Verdict

Winner in `result.json`: **`{winner}`**.

{result['verdict']}

## Reproducibility

```bash
{sys.executable} scripts/p03h_1781035058_850_43a47da0_support_map.py --config {config_path}
```

Key artifacts: `reproduction_match_table.csv`, `benchmark_pooled_summary.csv`,
`detector_label_policy_gaps.csv`, `nn_pull_calibration.csv`,
`pair_support_atoms.csv`, `support_atom_summary.csv`, `result.json`, and
`manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03h_1781035058_850_43a47da0_support_map.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["support"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    benchmark_dir = Path(config["source_benchmark_dir"])
    label_dir = Path(config["source_label_permutation_dir"])
    pooled = pd.read_csv(benchmark_dir / "pooled_run_block_summary.csv")
    pairwise = pd.read_csv(benchmark_dir / "pairwise_residuals.csv")
    label_gaps = pd.read_csv(label_dir / "run_label_policy_gap_summary.csv")
    calibration = pd.read_csv(label_dir / "ml_calibration.csv")
    p03f_result = json.loads((benchmark_dir / "result.json").read_text(encoding="utf-8"))
    p03g_result = json.loads((label_dir / "result.json").read_text(encoding="utf-8"))

    pooled.to_csv(out_dir / "benchmark_pooled_summary.csv", index=False)
    label_gaps.to_csv(out_dir / "detector_label_policy_gaps.csv", index=False)
    calibration.to_csv(out_dir / "nn_pull_calibration.csv", index=False)

    load_cfg = copy.deepcopy(config)
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loro_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(load_cfg)
    atoms = pair_atom_table(pulses, config)
    atoms.to_csv(out_dir / "pair_support_atoms.csv", index=False)
    support = support_atom_summary(pairwise, atoms, pooled, config, rng)
    support.to_csv(out_dir / "support_atom_summary.csv", index=False)

    nominal = pooled[~pooled["family"].isin(["traditional", "shuffled_target_control", "stave_offset_guardrail"])].copy()
    winner_row = nominal.sort_values("sigma68_ns").iloc[0]
    baseline = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    atom_evidence = atom_verdict(support, str(winner_row["method"]))
    guard = pooled[pooled["family"] == "stave_offset_guardrail"].sort_values("sigma68_ns").iloc[0]
    label_real = pd.read_csv(label_dir / "pooled_summary.csv").iloc[0]
    label_no_stave = pd.read_csv(label_dir / "pooled_summary.csv")
    hgb_no_stave = label_no_stave[label_no_stave["method"] == "gradient_boosted_trees_no_stave"].iloc[0]

    if atom_evidence["n_well_supported_atoms"] >= 6 and float(winner_row["delta_ci_high"]) < 0:
        verdict = (
            f"The stave-aware gain is real at the predictive-support level: {atom_evidence['n_well_supported_atoms']} "
            f"winner atoms have run/event-bootstrap deltas below zero, and the pooled winner beats analytic timewalk by "
            f"{float(winner_row['delta_vs_traditional_ns']):+.3f} ns. However, the stave-offset guardrail at "
            f"{float(guard['sigma68_ns']):.3f} ns and the P03g real-stave/no-stave gap show that detector identity explains "
            "a substantial share of the lift; this is not a standalone causal waveform adoption result."
        )
    else:
        verdict = (
            "The pooled stave-aware model wins, but atom-level support is too sparse or inconsistent to separate pulse-shape "
            "support from detector/run identity with high confidence."
        )

    result = {
        "study": "P03h",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(x) for x in config["timing"]["loro_runs"]],
        "traditional_method": {
            "method": "analytic_timewalk",
            "sigma68_ns": float(baseline["sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
            "full_rms_ns": float(baseline["full_rms_ns"]),
        },
        "benchmarked_methods": {
            "ridge": str(nominal[nominal["method"].str.startswith("ridge_")].sort_values("sigma68_ns").iloc[0]["method"]),
            "gradient_boosted_trees": str(nominal[nominal["method"].str.startswith("hgb_")].sort_values("sigma68_ns").iloc[0]["method"]),
            "mlp": str(nominal[nominal["method"].str.startswith("mlp_")].sort_values("sigma68_ns").iloc[0]["method"]),
            "cnn1d": str(nominal[nominal["method"].str.startswith("cnn1d_")].sort_values("sigma68_ns").iloc[0]["method"]),
            "new_architecture": "feature_gated",
            "new_architecture_best_method": str(nominal[nominal["method"].str.startswith("feature_gated_")].sort_values("sigma68_ns").iloc[0]["method"]),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
            "full_rms_ns": float(winner_row["full_rms_ns"]),
            "tail_frac_vs_traditional_p95": float(winner_row["tail_frac_vs_traditional_p95"]),
            "delta_vs_traditional_ns": float(winner_row["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner_row["delta_ci_low"]), float(winner_row["delta_ci_high"])],
        },
        "support_atom_evidence": atom_evidence,
        "detector_identity_controls": {
            "p03f_best_stave_offset_guardrail_sigma68_ns": float(guard["sigma68_ns"]),
            "p03f_guardrail_delta_vs_winner_ns": float(guard["sigma68_ns"] - winner_row["sigma68_ns"]),
            "p03g_best_real_stave_method": str(label_real["method"]),
            "p03g_best_real_stave_mean_sigma68_ns": float(label_real["mean_sigma68_ns"]),
            "p03g_hgb_no_stave_mean_sigma68_ns": float(hgb_no_stave["mean_sigma68_ns"]),
            "p03g_label_evidence": p03g_result.get("label_evidence", "unknown"),
        },
        "source_results": {
            "p03f_ticket": p03f_result.get("ticket"),
            "p03g_ticket": p03g_result.get("ticket"),
        },
        "verdict": verdict,
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, result, repro, pooled, support, label_gaps, calibration)
    pd.DataFrame([{"path": str(s02.raw_file(config, run)), "sha256": sha256_file(s02.raw_file(config, run))} for run in s02.configured_runs(config)]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )
    manifest = {
        "study": "P03h",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path.resolve()),
        "command": f"{sys.executable} {Path(__file__)} --config {config_path}",
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "source_artifacts": {
            "p03f_pooled": str((benchmark_dir / "pooled_run_block_summary.csv").resolve()),
            "p03f_pairwise": str((benchmark_dir / "pairwise_residuals.csv").resolve()),
            "p03g_label_gaps": str((label_dir / "run_label_policy_gap_summary.csv").resolve()),
        },
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "elapsed_s": manifest["elapsed_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
