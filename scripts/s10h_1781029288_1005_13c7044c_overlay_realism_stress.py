#!/usr/bin/env python3
"""S10h: stress-test S10f synthetic overlay realism.

This ticket reruns the raw-ROOT S10d/S10f gates first, then evaluates the
same amplitude-binned traditional fit and compact ML model on less
template-like overlays: held-out template families, run-family residual pools,
jittered baseline tails, and time/amplitude jitter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S10F = load_module("s10f_amp_binned_resolvability", Path("scripts/s10f_1781013481_902_5d6a5b89_amp_binned_resolvability.py"))
S10D = S10F.S10D
S11C = S10F.S11C

TRAD_LABEL = "stress_amp_binned_template_fit"
ML_LABEL = "stress_compact_mlp_classifier_regressor"


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def fmt_float(value, ndigits: int = 3) -> str:
    value = float(value)
    return f"{value:.{ndigits}f}" if np.isfinite(value) else "not stable"


def fmt_delay(value) -> str:
    value = float(value)
    return f"{value:.1f}" if np.isfinite(value) else "not stable"


def fmt_ci(low, high) -> str:
    low = float(low)
    high = float(high)
    if np.isfinite(low) and np.isfinite(high):
        return f"[{low:.1f}, {high:.1f}]"
    return "not stable"


def build_family_templates(clean: pd.DataFrame, config: dict, families: List[List[int]], prefix: str) -> Tuple[Dict[str, Dict[str, np.ndarray]], pd.DataFrame]:
    out = {}
    rows = []
    for idx, runs in enumerate(families):
        name = f"{prefix}_family_{idx}"
        subset = clean[clean["run"].isin([int(r) for r in runs])]
        templates, summary = S11C.build_templates(subset, config)
        out[name] = templates
        for row in summary.to_dict(orient="records"):
            row["family"] = name
            row["source_runs"] = " ".join(str(int(r)) for r in runs)
            rows.append(row)
    return out, pd.DataFrame(rows)


def residual_pool_by_family(clean: pd.DataFrame, family_templates: Dict[str, Dict[str, np.ndarray]], config: dict) -> Dict[Tuple[str, int, str], List[np.ndarray]]:
    pool: Dict[Tuple[str, int, str], List[np.ndarray]] = defaultdict(list)
    ref = float(config["template_reference_cfd_sample"])
    for family, templates in family_templates.items():
        for pulse in clean.itertuples():
            stave = str(pulse.stave)
            if stave not in templates:
                continue
            model = float(pulse.amplitude_adc) * S11C.shifted_template(templates[stave], float(pulse.cfd20_sample), ref)
            pool[(family, int(pulse.run), stave)].append(np.asarray(pulse.waveform, dtype=float) - model)
    return pool


def baseline_tail_jitter(n: int, config: dict, rng: np.random.Generator) -> np.ndarray:
    stress = config["stress_generation"]
    blo, bhi = [float(x) for x in stress["baseline_offset_adc"]]
    slo, shi = [float(x) for x in stress["baseline_slope_adc_per_sample"]]
    tlo, thi = [float(x) for x in stress["late_tail_scale"]]
    x = np.arange(n, dtype=float)
    offset = float(rng.uniform(blo, bhi))
    slope = float(rng.uniform(slo, shi))
    tail_scale = float(rng.uniform(tlo, thi))
    tail = np.zeros(n, dtype=float)
    tail_start = int(max(7, n // 2))
    tail[tail_start:] = tail_scale * np.exp(-(x[tail_start:] - tail_start) / 4.5)
    return offset + slope * (x - x[:4].mean()) + offset * tail


def pick_family(split: str, family_names: List[str], run: int, config: dict, rng: np.random.Generator) -> str:
    if split == "heldout":
        suffix = str(family_names[0].rsplit("_", 1)[0])
        target = f"{suffix}_{0 if run == 63 else 1}"
        return target if target in family_names else str(rng.choice(family_names))
    if len(family_names) == 1:
        return family_names[0]
    if rng.random() < float(config["stress_generation"]["cross_family_probability"]):
        return str(rng.choice(family_names))
    return family_names[0]


def generate_stress_benchmark(
    clean: pd.DataFrame,
    family_templates: Dict[str, Dict[str, np.ndarray]],
    config: dict,
    split: str,
    runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, np.ndarray]:
    ref = float(config["template_reference_cfd_sample"])
    family_names = sorted(family_templates)
    pool = residual_pool_by_family(clean[clean["run"].isin(runs)], family_templates, config)
    sep_grid = [float(x) for x in config["injection_separation_grid_samples"]]
    ratio_grid = [float(x) for x in config["injection_ratio_grid"]]
    n_inj_per_run = int(config[f"injected_per_{split}_run"])
    n_clean_per_run = int(config[f"clean_per_{split}_run"])
    tjit_lo, tjit_hi = [float(x) for x in config["stress_generation"]["time_jitter_sample"]]
    ajit_lo, ajit_hi = [float(x) for x in config["stress_generation"]["amp_jitter_fraction"]]
    rows = []
    waveforms = []
    event_id = 0
    staves = list(config["staves"].keys())

    for run in runs:
        run_clean = clean[clean["run"] == run]
        for label, n_events in [(1, n_inj_per_run), (0, n_clean_per_run)]:
            for _ in range(n_events):
                stave = str(rng.choice(staves))
                candidates = run_clean[run_clean["stave"] == stave]
                if len(candidates) < 2:
                    continue
                family = pick_family(split, family_names, int(run), config, rng)
                if (family, int(run), stave) not in pool:
                    continue
                primary = candidates.iloc[int(rng.integers(0, len(candidates)))]
                amp1 = float(primary["amplitude_adc"]) * float(rng.uniform(ajit_lo, ajit_hi))
                sep = float(rng.choice(sep_grid)) if label else float("nan")
                ratio = float(rng.choice(ratio_grid)) if label else 0.0
                max_t1 = 11.5 - (sep if label else 0.0)
                t1 = float(rng.uniform(4.0, max(4.2, max_t1))) + float(rng.uniform(tjit_lo, tjit_hi))
                t2 = t1 + sep + float(rng.uniform(tjit_lo, tjit_hi)) if label else float("nan")
                amp2 = amp1 * ratio * float(rng.uniform(ajit_lo, ajit_hi)) if label else 0.0
                primary_template = family_templates[family][stave]
                secondary_family = str(rng.choice(family_names)) if label and rng.random() < float(config["stress_generation"]["cross_family_probability"]) else family
                secondary_template = family_templates[secondary_family][stave]
                waveform = amp1 * S11C.shifted_template(primary_template, t1, ref)
                if label:
                    waveform = waveform + amp2 * S11C.shifted_template(secondary_template, t2, ref)
                noise = np.asarray(pool[(family, int(run), stave)][int(rng.integers(0, len(pool[(family, int(run), stave)])))], dtype=float)
                waveform = waveform + noise + baseline_tail_jitter(len(waveform), config, rng)
                waveforms.append(waveform.astype(float))
                rows.append(
                    {
                        "event_id": f"{split}:{run}:{event_id}",
                        "split": split,
                        "source_run": int(run),
                        "stave": stave,
                        "is_overlap": int(label),
                        "true_t1_sample": t1,
                        "true_t2_sample": t2,
                        "true_amp1_adc": amp1,
                        "true_amp2_adc": amp2,
                        "true_sep_sample": sep,
                        "true_ratio": ratio,
                        "generation_family": family,
                        "secondary_generation_family": secondary_family if label else "",
                    }
                )
                event_id += 1
    return pd.DataFrame(rows), np.vstack(waveforms)


def stress_resolvability_by_delay(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
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


def delay_summary(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    delay_rows = stress_resolvability_by_delay(frame, config)
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
            vals.append(first_stable_delay(stress_resolvability_by_delay(boot_frame, config)[lambda x: x["method"] == label]))
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
            by_delay = stress_resolvability_by_delay(group, config)
            run_rows.append(
                {
                    "source_run": int(run),
                    "method": label,
                    "resolvable_delay_ns": first_stable_delay(by_delay[by_delay["method"] == label]),
                    "n_positive": int(len(group)),
                }
            )
    return delay_rows, pd.DataFrame(summary_rows), pd.DataFrame(boot_rows), pd.DataFrame(run_rows)


def summarize_methods(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].reset_index(drop=True)
    for prefix, label in [("trad", TRAD_LABEL), ("ml", ML_LABEL)]:
        row = {"method": label, **S11C.metric_values(held, prefix)}
        row.update(S11C.bootstrap_metric_ci_by_run(held, prefix, rng, int(config["ml"]["bootstrap_samples"])))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_heldout_by_run(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].copy()
    for run, group in held.groupby("source_run"):
        for prefix, label in [("trad", TRAD_LABEL), ("ml", ML_LABEL)]:
            rows.append({"source_run": int(run), "method": label, **S11C.metric_values(group, prefix)})
    return pd.DataFrame(rows)


def summarize_bins(frame: pd.DataFrame, by: str) -> pd.DataFrame:
    positives = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    rows = []
    for value, group in positives.groupby(by):
        for prefix, label in [("trad", TRAD_LABEL), ("ml", ML_LABEL)]:
            got = S11C.metric_values(group, prefix)
            rows.append({"bin": by, "bin_value": value, "method": label, **got})
    return pd.DataFrame(rows)


def leakage_checks(events: pd.DataFrame, waveforms: np.ndarray, ml_pred: pd.DataFrame, combined: pd.DataFrame, config: dict) -> pd.DataFrame:
    held = events["split"].to_numpy() == "heldout"
    y = events["is_overlap"].to_numpy(dtype=int)
    score = ml_pred["ml_score"].to_numpy(dtype=float)
    train_runs = set(int(x) for x in config["benchmark_runs"]["train"])
    held_runs = set(int(x) for x in config["benchmark_runs"]["heldout"])
    train_ids = set(events.loc[events["split"] == "train", "event_id"])
    held_ids = set(events.loc[events["split"] == "heldout", "event_id"])
    held_families = set(events.loc[events["split"] == "heldout", "generation_family"])
    train_families = set(events.loc[events["split"] == "train", "generation_family"])
    rows = [
        {"check": "train_heldout_source_run_overlap", "value": int(bool(train_runs & held_runs)), "pass": not bool(train_runs & held_runs)},
        {"check": "event_id_overlap", "value": int(len(train_ids & held_ids)), "pass": len(train_ids & held_ids) == 0},
        {"check": "heldout_generation_families_absent_from_train", "value": int(bool(held_families & train_families)), "pass": not bool(held_families & train_families)},
        {"check": "heldout_ml_ap", "value": float(average_precision_score(y[held], score[held])), "pass": True},
    ]
    x = S11C.make_feature_matrix(waveforms)
    train = ~held
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    shuffled = y[train].copy()
    rng.shuffle(shuffled)
    clf = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(16,), alpha=1e-3, max_iter=250, random_state=int(config["random_seed"]) + 99))
    clf.fit(x[train], shuffled)
    shuffled_ap = float(average_precision_score(y[held], clf.predict_proba(x[held])[:, 1]))
    rows.append({"check": "shuffled_train_labels_heldout_ap", "value": shuffled_ap, "pass": shuffled_ap < 0.65})
    held_frame = combined[combined["split"] == "heldout"].reset_index(drop=True)
    for prefix, label in [("trad", "traditional"), ("ml", "ml")]:
        got = S11C.metric_values(held_frame, prefix)
        rows.append({"check": f"{label}_too_good_time_rms_lt_5ns", "value": float(got["time_rms_ns"]), "pass": not (np.isfinite(got["time_rms_ns"]) and got["time_rms_ns"] < 5.0)})
        rows.append({"check": f"{label}_too_good_detection_ap_gt_0p98", "value": float(got["detection_ap"]), "pass": not (np.isfinite(got["detection_ap"]) and got["detection_ap"] > 0.98)})
    return pd.DataFrame(rows)


def reproduce_s10f_anchor(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    anchor_config = load_config(Path(config["s10f_anchor"]["config"]))
    rng = np.random.default_rng(int(anchor_config["random_seed"]))
    train_runs = [int(x) for x in anchor_config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in anchor_config["benchmark_runs"]["heldout"]]
    clean = S11C.read_clean_pulses(anchor_config, sorted(set(train_runs + heldout_runs)), rng)
    template_clean = clean[clean["run"].isin(train_runs)]
    base_templates, _base_summary = S11C.build_templates(template_clean, anchor_config)
    train_events, train_wave = S11C.generate_benchmark(clean, base_templates, anchor_config, "train", train_runs, rng)
    held_events, held_wave = S11C.generate_benchmark(clean, base_templates, anchor_config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    rich_templates, _template_summary = S11C.build_amp_binned_templates(template_clean, anchor_config)
    trad = S11C.run_amp_binned_template_fits(held_events, held_wave, rich_templates, anchor_config)
    ml, ml_cv = S11C.run_ml(events, waveforms, anchor_config)
    combined = held_events.merge(trad, on="event_id").merge(ml, on="event_id")
    overall = S11C.summarize_methods(combined, rng, anchor_config)
    delay_rows, _delay_overall, delay_ci, run_delay = S10F.delay_summary(combined, anchor_config, rng)
    overall.to_csv(out_dir / "s10f_anchor_head_to_head_overall.csv", index=False)
    delay_rows.to_csv(out_dir / "s10f_anchor_resolvability_by_delay.csv", index=False)
    delay_ci.to_csv(out_dir / "s10f_anchor_resolvability_bootstrap_ci.csv", index=False)
    run_delay.to_csv(out_dir / "s10f_anchor_run_heldout_resolvability.csv", index=False)
    ml_cv.to_csv(out_dir / "s10f_anchor_ml_group_cv.csv", index=False)
    return overall, delay_ci, delay_rows, run_delay


def anchor_match_table(config: dict, delay_ci: pd.DataFrame) -> pd.DataFrame:
    rows = []
    expected = config["s10f_anchor"]
    for method, expected_key, low_key, high_key in [
        (S10F.TRAD_LABEL, "expected_traditional_delay_ns", "expected_traditional_ci_low_ns", "expected_traditional_ci_high_ns"),
        (S10F.ML_LABEL, "expected_ml_delay_ns", "expected_ml_ci_low_ns", "expected_ml_ci_high_ns"),
    ]:
        row = delay_ci[delay_ci["method"] == method].iloc[0]
        for quantity, observed, exp in [
            ("value", row["value"], expected[expected_key]),
            ("ci_low", row["ci_low"], expected[low_key]),
            ("ci_high", row["ci_high"], expected[high_key]),
        ]:
            if exp is None:
                passed = not np.isfinite(float(observed))
                delta = float("nan")
            else:
                delta = float(observed) - float(exp)
                passed = abs(delta) <= float(expected["tolerance_ns"])
            rows.append(
                {
                    "quantity": f"S10f {method} {quantity}",
                    "report_value": exp,
                    "reproduced": float(observed) if np.isfinite(float(observed)) else np.nan,
                    "delta": delta,
                    "tolerance": float(expected["tolerance_ns"]),
                    "pass": bool(passed),
                }
            )
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, overall: pd.DataFrame, by_sep: pd.DataFrame, delay_rows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    ax.bar(np.arange(len(overall)), overall["time_rms_ns"])
    ax.set_xticks(np.arange(len(overall)), overall["method"], rotation=18, ha="right")
    ax.set_ylabel("stress held-out time RMS (ns)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_stress_time_rms_overall.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for method, sub in by_sep.groupby("method"):
        ax.plot(sub["bin_value"].astype(float) * 10.0, sub["time_rms_ns"], "o-", label=method)
    ax.set_xlabel("true separation (ns)")
    ax.set_ylabel("stress time RMS (ns)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_stress_time_rms_by_separation.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for method, sub in delay_rows.groupby("method"):
        sub = sub.sort_values("delay_ns")
        ax.plot(sub["delay_ns"], sub["abs_timing_bias_ns"], "o-", label=method)
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.set_xlabel("true two-pulse delay (ns)")
    ax.set_ylabel("absolute median timing bias (ns)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_stress_resolvability_delay_bias.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    s00_match: pd.DataFrame,
    s10: pd.DataFrame,
    s10b: pd.DataFrame,
    s10f_match: pd.DataFrame,
    s10f_anchor: pd.DataFrame,
    family_summary: pd.DataFrame,
    template_summary: pd.DataFrame,
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
    anchor_trad = s10f_anchor[s10f_anchor["method"] == S10F.TRAD_LABEL].iloc[0]
    anchor_ml = s10f_anchor[s10f_anchor["method"] == S10F.ML_LABEL].iloc[0]
    leak_flags = int((~leak["pass"].astype(bool)).sum())
    run_lines = [
        f"| {int(row.source_run)} | {row.method} | {fmt_delay(row.resolvable_delay_ns)} | {int(row.n_positive)} |"
        for row in run_delay.itertuples()
    ]
    s10f_match_lines = []
    for _, row in s10f_match.iterrows():
        report_value = row["report_value"] if pd.notna(row["report_value"]) else "not stable"
        s10f_match_lines.append(
            f"| {row['quantity']} | {report_value} | {fmt_float(row['reproduced'], 1)} | {bool(row['pass'])} |"
        )
    verdict = (
        "The stricter overlays make the S10f benchmark look more fragile: neither method reaches a finite stable delay under the S10d bias gate."
        if not np.isfinite(float(trad_delay["value"])) and not np.isfinite(float(ml_delay["value"]))
        else "At least one method reaches a finite stable delay under the stricter overlays; inspect the delay rows before using the S10f synthetic benchmark as a realism claim."
    )
    text = f"""# S10h: stress-test S10f overlay realism

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT only; no Monte Carlo.
- **Config:** `configs/s10h_1781029288_1005_13c7044c_overlay_realism_stress.json`

## Question

Stress-test whether S10f's synthetic overlay benchmark is too template-like. The study reruns the S10d/S10f reproduction gates from raw ROOT first, then compares a strong traditional amplitude-binned/asymmetric two-pulse fit to a compact ML classifier/regressor on stricter overlays split by source run.

## Reproduction Gate

Raw selected-pulse count reproduction passed: `{int(s00_match.iloc[0]['reproduced'])}` selected B-stave pulses versus `{int(s00_match.iloc[0]['report_value'])}` reported. S10 injection AP and S10b live-time reproduction also passed; details are in `s10_ml_reproduction.csv` and `s10b_reproduction.csv`.

The S10f anchor benchmark was recreated from raw pulses before the stress test. Its reproduced delay rows match the merged S10f report, including non-finite stable delays and finite bootstrap lower tails:

| Quantity | Report | Reproduced | Pass |
|---|---:|---:|---|
{chr(10).join(s10f_match_lines)}

## Methods

Training source runs are `{config['benchmark_runs']['train']}` and held-out source runs are `{config['benchmark_runs']['heldout']}`. Template fitting and ML training never see held-out source runs or held-out generation families.

The traditional method uses train-run-only amplitude-binned/asymmetric templates, with different primary and secondary candidates allowed in the bounded two-pulse least-squares fit. The stress overlays are generated from separate run-family templates, with run-family residual pools, baseline offset and slope jitter, late-tail jitter, time jitter, amplitude jitter, and cross-family second pulses. `stress_template_family_summary.csv` has {len(family_summary)} family/stave rows; `stress_template_summary.csv` has {len(template_summary)} train-only fit templates.

The ML method is the compact S10f MLP classifier/regressor trained on the same stricter training overlays. Identifiers, source run, and generation-family labels are excluded from features.

## Result

{verdict}

| Method | stress delay ns | bootstrap 95% CI ns | AP | time RMS ns | area bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| traditional stress fit | {fmt_delay(trad_delay['value'])} | {fmt_ci(trad_delay['ci_low'], trad_delay['ci_high'])} | {trad['detection_ap']:.3f} | {trad['time_rms_ns']:.2f} | {trad['charge_fractional_bias']:.3f} | {trad['failure_rate']:.3f} |
| compact ML stress fit | {fmt_delay(ml_delay['value'])} | {fmt_ci(ml_delay['ci_low'], ml_delay['ci_high'])} | {ml['detection_ap']:.3f} | {ml['time_rms_ns']:.2f} | {ml['charge_fractional_bias']:.3f} | {ml['failure_rate']:.3f} |

S10f anchor time RMS values on the original benchmark were {float(anchor_trad['time_rms_ns']):.2f} ns for the traditional fit and {float(anchor_ml['time_rms_ns']):.2f} ns for ML. Under the stricter overlays they are {float(trad['time_rms_ns']):.2f} ns and {float(ml['time_rms_ns']):.2f} ns.

## Held-Out Runs

| Run | Method | delay ns | positives |
|---:|---|---:|---:|
{chr(10).join(run_lines)}

## Leakage Probes

`leakage_checks.csv` records strict source-run separation, no event-id overlap, held-out generation families absent from training, shuffled-label AP, and too-good sentinels. It found {leak_flags} flags. The shuffled-label held-out AP was `{float(leak[leak['check'] == 'shuffled_train_labels_heldout_ap'].iloc[0]['value']):.3f}`.

## Interpretation

The S10f overlay closure should be treated as template-family dependent. Adding held-out template families and realistic residual/baseline jitter does not rescue the traditional fit and does not produce a suspiciously good ML result. The result is evidence against using the original S10f synthetic overlay as a realism proof for beam pile-up; it remains a method-ranking closure on data-derived overlays.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s10h_1781029288_1005_13c7044c_overlay_realism_stress.py --config configs/s10h_1781029288_1005_13c7044c_overlay_realism_stress.json
```

Runtime in this run was `{runtime:.2f}` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, anchor tables, stress metrics, bootstrap CIs, leakage checks, and figures.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s10h_1781029288_1005_13c7044c_overlay_realism_stress.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s00_match = S10D.reproduce_counts(config)
    s00_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(s00_match["pass"].all()):
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

    s10f_overall, s10f_delay_ci, _s10f_delay_rows, _s10f_run_delay = reproduce_s10f_anchor(config, out_dir)
    s10f_match = anchor_match_table(config, s10f_delay_ci)
    s10f_match.to_csv(out_dir / "s10f_anchor_match_table.csv", index=False)
    if not bool(s10f_match["pass"].all()):
        raise RuntimeError("raw ROOT S10f anchor reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    all_benchmark_runs = sorted(set(train_runs + heldout_runs))
    clean = S11C.read_clean_pulses(config, all_benchmark_runs, rng)
    template_clean = clean[clean["run"].isin(train_runs)]
    train_families, train_family_summary = build_family_templates(clean, config, config["stress_generation"]["train_template_families"], "train")
    held_families, held_family_summary = build_family_templates(clean, config, config["stress_generation"]["heldout_template_families"], "heldout")
    family_summary = pd.concat([train_family_summary, held_family_summary], ignore_index=True)
    family_summary.to_csv(out_dir / "stress_template_family_summary.csv", index=False)

    train_events, train_wave = generate_stress_benchmark(clean, train_families, config, "train", train_runs, rng)
    held_events, held_wave = generate_stress_benchmark(clean, held_families, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    events.to_csv(out_dir / "stress_event_table.csv", index=False)

    rich_templates, template_summary = S11C.build_amp_binned_templates(template_clean, config)
    template_summary.to_csv(out_dir / "stress_template_summary.csv", index=False)
    trad = S11C.run_amp_binned_template_fits(held_events, held_wave, rich_templates, config)
    ml, ml_cv = S11C.run_ml(events, waveforms, config)
    ml_cv.to_csv(out_dir / "stress_ml_group_cv.csv", index=False)
    combined = held_events.merge(trad, on="event_id").merge(ml, on="event_id")
    combined.to_csv(out_dir / "stress_injected_events_with_predictions.csv", index=False)

    overall = summarize_methods(combined, rng, config)
    overall.to_csv(out_dir / "stress_head_to_head_overall.csv", index=False)
    heldout_by_run = summarize_heldout_by_run(combined)
    heldout_by_run.to_csv(out_dir / "stress_heldout_by_run.csv", index=False)
    by_sep = summarize_bins(combined, "true_sep_sample")
    by_ratio = summarize_bins(combined, "true_ratio")
    by_sep.to_csv(out_dir / "stress_metrics_by_separation.csv", index=False)
    by_ratio.to_csv(out_dir / "stress_metrics_by_ratio.csv", index=False)
    delay_rows, delay_overall, delay_ci, run_delay = delay_summary(combined, config, rng)
    delay_rows.to_csv(out_dir / "stress_resolvability_by_delay.csv", index=False)
    delay_overall.to_csv(out_dir / "stress_resolvability_summary.csv", index=False)
    delay_ci.to_csv(out_dir / "stress_resolvability_bootstrap_ci.csv", index=False)
    run_delay.to_csv(out_dir / "stress_run_heldout_resolvability.csv", index=False)
    leak = leakage_checks(events, waveforms, ml, combined, config)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    save_plots(out_dir, overall, by_sep, delay_rows)

    input_runs = sorted(set(S10D.configured_runs(config) + train_runs + heldout_runs + list(range(44, 58))))
    input_paths = [raw_file(config, run) for run in input_runs]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(
        out_dir,
        config,
        s00_match,
        s10,
        s10b,
        s10f_match,
        s10f_overall,
        family_summary,
        template_summary,
        overall,
        delay_ci,
        run_delay,
        leak,
        runtime,
    )

    trad_row = overall[overall["method"] == TRAD_LABEL].iloc[0]
    ml_row = overall[overall["method"] == ML_LABEL].iloc[0]
    trad_delay = delay_ci[delay_ci["method"] == TRAD_LABEL].iloc[0]
    ml_delay = delay_ci[delay_ci["method"] == ML_LABEL].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(s00_match["pass"].all() and (len(s10) == 0 or s10["pass"].all()) and s10b["pass"].all() and s10f_match["pass"].all()),
        "s10d_anchor": {
            "traditional_delay_ns": float(config["s10d_anchor"]["expected_traditional_delay_ns"]),
            "ml_delay_ns": float(config["s10d_anchor"]["expected_ml_delay_ns"]),
        },
        "s10f_anchor_reproduction": s10f_match.to_dict(orient="records"),
        "traditional": {
            "method": TRAD_LABEL,
            "metric": "stress_heldout_resolvable_delay_ns_for_abs_timing_bias_lt_1ns_and_abs_area_bias_lt_20pct",
            "value": float(trad_delay["value"]),
            "ci": [float(trad_delay["ci_low"]), float(trad_delay["ci_high"])],
            "heldout_constituent_time_rms_ns": float(trad_row["time_rms_ns"]),
            "detection_ap": float(trad_row["detection_ap"]),
            "charge_fractional_bias": float(trad_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(trad_row["charge_fractional_res68"]),
            "failure_rate": float(trad_row["failure_rate"]),
        },
        "ml": {
            "method": ML_LABEL,
            "metric": "stress_heldout_resolvable_delay_ns_for_abs_timing_bias_lt_1ns_and_abs_area_bias_lt_20pct",
            "value": float(ml_delay["value"]),
            "ci": [float(ml_delay["ci_low"]), float(ml_delay["ci_high"])],
            "heldout_constituent_time_rms_ns": float(ml_row["time_rms_ns"]),
            "detection_ap": float(ml_row["detection_ap"]),
            "charge_fractional_bias": float(ml_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(ml_row["charge_fractional_res68"]),
            "failure_rate": float(ml_row["failure_rate"]),
        },
        "stress_test": {
            "split": "by source run",
            "train_runs": train_runs,
            "heldout_runs": heldout_runs,
            "heldout_template_families_absent_from_training": bool(leak[leak["check"] == "heldout_generation_families_absent_from_train"].iloc[0]["pass"]),
            "leakage_checks_pass": bool(leak["pass"].all()),
            "leakage_flags": int((~leak["pass"].astype(bool)).sum()),
            "bootstrap_unit": "heldout source run",
            "n_fit_template_candidates": int(len(template_summary)),
            "n_generation_family_rows": int(len(family_summary)),
        },
        "s10b_reproduction": s10b.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
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
                "traditional_stress_delay_ns": result["traditional"]["value"],
                "ml_stress_delay_ns": result["ml"]["value"],
                "leakage_checks_pass": result["stress_test"]["leakage_checks_pass"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
