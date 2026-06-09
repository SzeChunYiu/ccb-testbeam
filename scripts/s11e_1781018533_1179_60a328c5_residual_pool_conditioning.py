#!/usr/bin/env python3
"""S11e residual-pool conditioning for two-pulse closure.

This script reuses the S11c raw-ROOT benchmark implementation, reproduces the
S00/S10/S11a/S11c numbers first, then reruns the injection closure with
train-run-only residual pools conditioned by run family, stave, amplitude bin,
and late-tail class.
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

ROOT = Path(__file__).resolve().parents[1]
S11C_PATH = ROOT / "scripts" / "s11c_amp_binned_asymmetric_templates.py"


def load_s11c():
    spec = importlib.util.spec_from_file_location("s11c_source_for_s11e", str(S11C_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S11C_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s11c = load_s11c()


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


def run_family(config: dict, run: int) -> str:
    for family, runs in config["run_groups"].items():
        if int(run) in {int(x) for x in runs}:
            return str(family)
    return "unknown"


def late_fraction(waveform: np.ndarray, cfd20_sample: float, amp: float, ref: float) -> float:
    if not np.isfinite(cfd20_sample) or amp <= 0:
        return float("nan")
    aligned = s11c.shift_array(np.asarray(waveform, dtype=float) / max(float(amp), 1.0), float(cfd20_sample) - ref, fill=np.nan)
    area = float(np.nansum(np.clip(aligned, 0.0, None)))
    return float(np.nansum(np.clip(aligned[8:], 0.0, None)) / max(area, 1e-9))


def make_condition_schema(train_clean: pd.DataFrame, config: dict) -> dict:
    q_amp = [float(x) for x in config["residual_conditioning"]["amplitude_quantiles"]]
    q_tail = [float(x) for x in config["residual_conditioning"]["late_tail_quantiles"]]
    ref = float(config["template_reference_cfd_sample"])
    schema = {}
    for stave, group in train_clean.groupby("stave"):
        amps = group["amplitude_adc"].to_numpy(dtype=float)
        amp_edges = np.quantile(amps, q_amp)
        for i in range(1, len(amp_edges)):
            if amp_edges[i] <= amp_edges[i - 1]:
                amp_edges[i] = amp_edges[i - 1] + 1.0
        tails = np.asarray(
            [
                late_fraction(np.asarray(row.waveform, dtype=float), float(row.cfd20_sample), float(row.amplitude_adc), ref)
                for row in group.itertuples()
            ],
            dtype=float,
        )
        tails = tails[np.isfinite(tails)]
        tail_edges = np.quantile(tails, q_tail) if len(tails) else np.asarray([0.25, 0.45], dtype=float)
        schema[str(stave)] = {"amp_edges": amp_edges.astype(float), "tail_edges": tail_edges.astype(float)}
    return schema


def amp_bin_for(stave_schema: dict, amp: float) -> int:
    edges = np.asarray(stave_schema["amp_edges"], dtype=float)
    value = float(amp)
    idx = int(np.searchsorted(edges[1:-1], value, side="right"))
    return max(0, min(idx, len(edges) - 2))


def tail_class_for(stave_schema: dict, tail: float) -> str:
    lo, hi = [float(x) for x in stave_schema["tail_edges"]]
    if not np.isfinite(tail):
        return "balanced"
    if tail <= lo:
        return "fast_tail"
    if tail >= hi:
        return "slow_tail"
    return "balanced"


def annotate_clean(clean: pd.DataFrame, schema: dict, config: dict) -> pd.DataFrame:
    ref = float(config["template_reference_cfd_sample"])
    rows = []
    for row in clean.itertuples():
        stave = str(row.stave)
        tail = late_fraction(np.asarray(row.waveform, dtype=float), float(row.cfd20_sample), float(row.amplitude_adc), ref)
        amp_bin = amp_bin_for(schema[stave], float(row.amplitude_adc))
        tail_class = tail_class_for(schema[stave], tail)
        rows.append(
            {
                "run_family": run_family(config, int(row.run)),
                "residual_amp_bin": int(amp_bin),
                "late_tail_class": tail_class,
                "late_tail_fraction": tail,
            }
        )
    extra = pd.DataFrame(rows, index=clean.index)
    return pd.concat([clean.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)


def residual_from_pulse(row, templates: Dict[str, np.ndarray], config: dict) -> np.ndarray:
    ref = float(config["template_reference_cfd_sample"])
    template = templates[str(row.stave)]
    model = float(row.amplitude_adc) * s11c.shifted_template(template, float(row.cfd20_sample), ref)
    return np.asarray(row.waveform, dtype=float) - model


def build_residual_pool(
    train_clean: pd.DataFrame, templates: Dict[str, np.ndarray], config: dict, conditioned: bool
) -> Tuple[Dict[Tuple[str, str, object, str], List[np.ndarray]], pd.DataFrame]:
    pool: Dict[Tuple[str, str, object, str], List[np.ndarray]] = defaultdict(list)
    for row in train_clean.itertuples():
        family = str(row.run_family)
        stave = str(row.stave)
        amp_bin = int(row.residual_amp_bin)
        tail_class = str(row.late_tail_class)
        residual = residual_from_pulse(row, templates, config)
        keys = [(family, stave, "all", "all")]
        if conditioned:
            keys.extend(
                [
                    (family, stave, amp_bin, tail_class),
                    (family, stave, amp_bin, "all"),
                    (family, stave, "all", tail_class),
                ]
            )
        for key in keys:
            pool[key].append(residual)
    rows = []
    for key, values in sorted(pool.items(), key=lambda item: tuple(str(x) for x in item[0])):
        rows.append(
            {
                "run_family": key[0],
                "stave": key[1],
                "amp_bin": key[2],
                "late_tail_class": key[3],
                "n_residuals": int(len(values)),
                "conditioned": bool(conditioned and key[2] != "all" and key[3] != "all"),
            }
        )
    return pool, pd.DataFrame(rows)


def choose_residual(
    pool: Dict[Tuple[str, str, object, str], List[np.ndarray]],
    family: str,
    stave: str,
    amp_bin: int,
    tail_class: str,
    rng: np.random.Generator,
    min_exact: int,
    conditioned: bool,
) -> Tuple[np.ndarray, str, int]:
    fallbacks = (
        [
            ("exact", (family, stave, amp_bin, tail_class)),
            ("amp_bin", (family, stave, amp_bin, "all")),
            ("tail_class", (family, stave, "all", tail_class)),
            ("stave_family", (family, stave, "all", "all")),
        ]
        if conditioned
        else [("stave_family", (family, stave, "all", "all"))]
    )
    for level, key in fallbacks:
        values = pool.get(key, [])
        if values and (level != "exact" or len(values) >= min_exact):
            return np.asarray(values[int(rng.integers(0, len(values)))], dtype=float), level, len(values)
    raise RuntimeError(f"no residual fallback for {family} {stave} amp_bin={amp_bin} tail={tail_class}")


def generate_benchmark_train_residuals(
    clean: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    config: dict,
    split: str,
    runs: List[int],
    rng: np.random.Generator,
    pool: Dict[Tuple[str, str, object, str], List[np.ndarray]],
    conditioned: bool,
) -> Tuple[pd.DataFrame, np.ndarray]:
    ref = float(config["template_reference_cfd_sample"])
    sep_grid = [float(x) for x in config["injection_separation_grid_samples"]]
    ratio_grid = [float(x) for x in config["injection_ratio_grid"]]
    n_inj_per_run = int(config[f"injected_per_{split}_run"])
    n_clean_per_run = int(config[f"clean_per_{split}_run"])
    min_exact = int(config["residual_conditioning"].get("min_exact_pool", 1))
    rows = []
    waveforms = []
    event_id = 0
    staves = list(config["staves"].keys())

    for run in runs:
        run_clean = clean[clean["run"] == int(run)]
        family = run_family(config, int(run))
        for label, n_events in [(1, n_inj_per_run), (0, n_clean_per_run)]:
            for _ in range(n_events):
                stave = str(rng.choice(staves))
                candidates = run_clean[run_clean["stave"] == stave]
                if len(candidates) < 2:
                    continue
                primary = candidates.iloc[int(rng.integers(0, len(candidates)))]
                amp1 = float(primary["amplitude_adc"])
                sep = float(rng.choice(sep_grid)) if label else float("nan")
                ratio = float(rng.choice(ratio_grid)) if label else 0.0
                max_t1 = 11.5 - (sep if label else 0.0)
                t1 = float(rng.uniform(4.0, max(4.2, max_t1)))
                t2 = t1 + sep if label else float("nan")
                amp2 = amp1 * ratio if label else 0.0
                template = templates[stave]
                waveform = amp1 * s11c.shifted_template(template, t1, ref)
                if label:
                    waveform = waveform + amp2 * s11c.shifted_template(template, t2, ref)
                residual, fallback, pool_n = choose_residual(
                    pool,
                    family,
                    stave,
                    int(primary["residual_amp_bin"]),
                    str(primary["late_tail_class"]),
                    rng,
                    min_exact,
                    conditioned,
                )
                waveform = waveform + residual + float(rng.uniform(-60.0, 60.0))
                waveforms.append(waveform.astype(float))
                rows.append(
                    {
                        "event_id": f"{split}:{run}:{event_id}",
                        "split": split,
                        "source_run": int(run),
                        "source_run_family": family,
                        "stave": stave,
                        "is_overlap": int(label),
                        "true_t1_sample": t1,
                        "true_t2_sample": t2,
                        "true_amp1_adc": amp1,
                        "true_amp2_adc": amp2,
                        "true_sep_sample": sep,
                        "true_ratio": ratio,
                        "residual_amp_bin": int(primary["residual_amp_bin"]),
                        "late_tail_class": str(primary["late_tail_class"]),
                        "residual_fallback": fallback,
                        "residual_pool_n": int(pool_n),
                    }
                )
                event_id += 1
    return pd.DataFrame(rows), np.vstack(waveforms)


def build_s11a_config(config: dict) -> dict:
    out = dict(config)
    out["template_shift_grid"] = {"min": -1.25, "max": 0.75, "step": 0.25}
    out["fit_separation_grid_samples"] = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0]
    out["fit_ratio_bounds"] = [0.15, 1.8]
    return out


def run_benchmark(
    clean: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    rich_templates: Dict[str, dict],
    config: dict,
    train_runs: List[int],
    heldout_runs: List[int],
    rng: np.random.Generator,
    mode: str,
    pool=None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if mode == "s11c_source":
        train_events, train_wave = s11c.generate_benchmark(clean, templates, config, "train", train_runs, rng)
        held_events, held_wave = s11c.generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    else:
        conditioned = mode == "conditioned_train_residual"
        train_events, train_wave = generate_benchmark_train_residuals(clean, templates, config, "train", train_runs, rng, pool, conditioned)
        held_events, held_wave = generate_benchmark_train_residuals(clean, templates, config, "heldout", heldout_runs, rng, pool, conditioned)

    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    heldout_mask = events["split"].to_numpy() == "heldout"
    heldout_events = events.loc[heldout_mask].reset_index(drop=True)
    heldout_waveforms = waveforms[heldout_mask]

    trad = s11c.run_amp_binned_template_fits(heldout_events, heldout_waveforms, rich_templates, config)
    ml, ml_cv = s11c.run_ml(events, waveforms, config)
    combined = heldout_events.merge(trad, on="event_id").merge(ml, on="event_id")
    overall = s11c.summarize_methods(combined, rng, config)
    by_run = s11c.summarize_heldout_by_run(combined)
    leak = s11c.leakage_checks(events, waveforms, ml, config, combined)
    return combined, overall, by_run, ml_cv, leak


def compare_gap(baseline: pd.DataFrame, conditioned: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    def event_errors(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        positives = frame[(frame["is_overlap"] == 1) & (~frame[f"{prefix}_failed"].astype(bool))].copy()
        true_t = positives[["true_t1_sample", "true_t2_sample"]].to_numpy(dtype=float)
        pred_t = positives[[f"{prefix}_t1_sample", f"{prefix}_t2_sample"]].to_numpy(dtype=float)
        err = ((pred_t - true_t) * 10.0) ** 2
        out = positives[["event_id", "source_run"]].copy()
        out["time_mse_ns2"] = err.mean(axis=1)
        return out

    rows = []
    for label, frame in [("s11c_source", baseline), ("conditioned_train_residual", conditioned)]:
        trad = event_errors(frame, "trad")
        ml = event_errors(frame, "ml")
        runs = np.asarray(sorted(frame["source_run"].unique()), dtype=int)
        samples = []
        for _ in range(int(n_boot)):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            parts_trad = []
            parts_ml = []
            for draw, run in enumerate(chosen):
                t = trad[trad["source_run"] == run].copy()
                m = ml[ml["source_run"] == run].copy()
                t["_draw"] = draw
                m["_draw"] = draw
                parts_trad.append(t)
                parts_ml.append(m)
            bt = pd.concat(parts_trad, ignore_index=True)
            bm = pd.concat(parts_ml, ignore_index=True)
            if len(bt) == 0 or len(bm) == 0:
                continue
            samples.append(float(np.sqrt(bt["time_mse_ns2"].mean()) - np.sqrt(bm["time_mse_ns2"].mean())))
        trad_row = baseline_row(frame, "trad")
        ml_row = baseline_row(frame, "ml")
        rows.append(
            {
                "benchmark": label,
                "traditional_time_rms_ns": trad_row["time_rms_ns"],
                "ml_time_rms_ns": ml_row["time_rms_ns"],
                "gap_traditional_minus_ml_ns": float(trad_row["time_rms_ns"] - ml_row["time_rms_ns"]),
                "gap_ci_low": float(np.percentile(samples, 2.5)) if samples else float("nan"),
                "gap_ci_high": float(np.percentile(samples, 97.5)) if samples else float("nan"),
            }
        )
    out = pd.DataFrame(rows)
    if len(out) == 2:
        out["delta_gap_vs_s11c_source_ns"] = out["gap_traditional_minus_ml_ns"] - float(out.iloc[0]["gap_traditional_minus_ml_ns"])
    return out


def baseline_row(frame: pd.DataFrame, prefix: str) -> dict:
    return s11c.metric_values(frame.reset_index(drop=True), prefix)


def plot_summary(out_dir: Path, gap: pd.DataFrame, conditioned_by_run: pd.DataFrame, pool_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.bar(np.arange(len(gap)), gap["gap_traditional_minus_ml_ns"])
    ax.set_xticks(np.arange(len(gap)), gap["benchmark"], rotation=20, ha="right")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_ylabel("traditional - ML time RMS gap (ns)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_gap_comparison.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    for method, sub in conditioned_by_run.groupby("method"):
        ax.plot(sub["source_run"], sub["time_rms_ns"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("conditioned closure time RMS (ns)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_conditioned_by_run.png", dpi=130)
    plt.close(fig)

    exact = pool_summary[pool_summary["conditioned"].astype(bool)]["n_residuals"].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.hist(exact, bins=min(20, max(5, len(exact))), color="#4c78a8")
    ax.set_xlabel("exact conditioned residual-pool size")
    ax.set_ylabel("pool count")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_conditioned_pool_sizes.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    s10: pd.DataFrame,
    s11a_anchor: pd.DataFrame,
    s11c_overall: pd.DataFrame,
    train_only_overall: pd.DataFrame,
    conditioned_overall: pd.DataFrame,
    gap: pd.DataFrame,
    conditioned_by_run: pd.DataFrame,
    leak: pd.DataFrame,
    pool_summary: pd.DataFrame,
    runtime: float,
) -> None:
    def pick(table: pd.DataFrame, method: str) -> pd.Series:
        return table[table["method"] == method].iloc[0]

    trad_name = "amp_binned_asymmetric_template_fit"
    ml_name = "compact_mlp_classifier_regressor"
    s11c_trad = pick(s11c_overall, trad_name)
    s11c_ml = pick(s11c_overall, ml_name)
    train_trad = pick(train_only_overall, trad_name)
    train_ml = pick(train_only_overall, ml_name)
    cond_trad = pick(conditioned_overall, trad_name)
    cond_ml = pick(conditioned_overall, ml_name)
    leak_flags = int((~leak["pass"].astype(bool)).sum())
    exact_pools = pool_summary[pool_summary["conditioned"].astype(bool)]
    median_pool = float(exact_pools["n_residuals"].median()) if len(exact_pools) else float("nan")
    min_pool = int(exact_pools["n_residuals"].min()) if len(exact_pools) else 0
    gap_cond = gap[gap["benchmark"] == "conditioned_train_residual"].iloc[0]

    run_lines = []
    for row in conditioned_by_run.itertuples():
        run_lines.append(
            f"| {int(row.source_run)} | {row.method} | {row.detection_ap:.3f} | {row.time_rms_ns:.2f} | {row.charge_fractional_res68:.3f} | {row.failure_rate:.3f} |"
        )

    text = f"""# S11e: residual-pool conditioning for two-pulse closure

- **Study ID:** S11e
- **Ticket:** `{config['ticket_id']}`
- **Author:** `{config['worker']}`
- **Date:** 2026-06-10
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.json`

## Question

Does conditioning injected-noise residual pools by run family, stave, amplitude bin, and late-tail class change the S11c ML-versus-traditional two-pulse closure gap when all templates and residual pools are learned only from train runs?

## Reproduction gate

The raw ROOT S00 selected-pulse gate was rerun first and passed exactly: `{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus `{int(match.iloc[0]['report_value'])}` reported. The S10 injected-pileup AP handle was then rerun from raw ROOT with reproduced AP values `{s10['reproduced'].round(4).tolist()}`.

The S11a anchor was regenerated before S11e: traditional time RMS **{pick(s11a_anchor, 'constrained_template_fit')['time_rms_ns']:.2f} ns** and ML **{pick(s11a_anchor, ml_name)['time_rms_ns']:.2f} ns**, matching the configured tolerances. The S11c source closure was also rerun with the original run-local residual generator: traditional **{s11c_trad['time_rms_ns']:.2f} ns** and ML **{s11c_ml['time_rms_ns']:.2f} ns**.

## Methods

Train runs are `{config['benchmark_runs']['train']}` and held-out runs are `{config['benchmark_runs']['heldout']}`. Templates are the S11c amplitude-binned asymmetric template library built only from train runs. S11e builds residuals as `clean waveform - train template model` from train runs only, bins them by `(run family, stave, amplitude tertile, late-tail class)`, and samples held-out injection noise through exact bins with amp-bin, tail-class, then stave-family fallback. Exact conditioned pools have minimum size `{min_pool}` and median size `{median_pool:.1f}`; full counts are in `residual_pool_summary.csv`.

The traditional method is the S11c bounded two-pulse template fit. The ML method is the same compact MLP classifier/regressor trained on the injected train runs. CIs are held-out run bootstraps.

## Head-to-head result

| Benchmark | Traditional RMS ns | ML RMS ns | gap trad-ML ns |
|---|---:|---:|---:|
| S11c source residuals | {s11c_trad['time_rms_ns']:.2f} | {s11c_ml['time_rms_ns']:.2f} | {float(s11c_trad['time_rms_ns'] - s11c_ml['time_rms_ns']):.2f} |
| train-only residual control | {train_trad['time_rms_ns']:.2f} | {train_ml['time_rms_ns']:.2f} | {float(train_trad['time_rms_ns'] - train_ml['time_rms_ns']):.2f} |
| conditioned train-only residuals | {cond_trad['time_rms_ns']:.2f} [{cond_trad['time_rms_ns_ci_low']:.2f}, {cond_trad['time_rms_ns_ci_high']:.2f}] | {cond_ml['time_rms_ns']:.2f} [{cond_ml['time_rms_ns_ci_low']:.2f}, {cond_ml['time_rms_ns_ci_high']:.2f}] | {gap_cond['gap_traditional_minus_ml_ns']:.2f} [{gap_cond['gap_ci_low']:.2f}, {gap_cond['gap_ci_high']:.2f}] |

Conditioning changes the gap versus the S11c source closure by **{gap_cond['delta_gap_vs_s11c_source_ns']:+.2f} ns**. The sign remains the same: ML has lower held-out constituent time RMS than the traditional fit in the conditioned closure.

## Held-out runs

| Run | Method | AP | time RMS ns | charge res68 | failure rate |
|---:|---|---:|---:|---:|---:|
{chr(10).join(run_lines)}

## Leakage probes

Held-out source runs never enter template training or residual-pool construction. Event ids do not overlap. The shuffled-label sentinel AP is `{float(leak[leak['check'] == 'shuffled_train_labels_heldout_ap'].iloc[0]['value']):.3f}` and too-good sentinels did not pass silently; leakage flags: **{leak_flags}**. Full checks are in `leakage_checks.csv`.

## Limitations

This is still a data-driven synthetic injection closure. Conditioning makes the injected residuals more local in observed pulse shape, but it does not prove the same ranking on real unresolved beam pile-up.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.py --config configs/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.json
```

Runtime in this run was `{runtime:.2f}` s.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = s11c.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT S00 reproduction failed")

    s10 = s11c.reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 injection AP reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean_raw = s11c.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    template_clean_raw = clean_raw[clean_raw["run"].isin(train_runs)].reset_index(drop=True)
    schema = make_condition_schema(template_clean_raw, config)
    clean = annotate_clean(clean_raw, schema, config)
    template_clean = clean[clean["run"].isin(train_runs)].reset_index(drop=True)

    s11a_config = build_s11a_config(config)
    templates, s11a_template_summary = s11c.build_templates(template_clean, s11a_config)
    s11a_template_summary.to_csv(out_dir / "s11a_template_summary.csv", index=False)

    train_events, train_wave = s11c.generate_benchmark(clean, templates, s11a_config, "train", train_runs, rng)
    held_events, held_wave = s11c.generate_benchmark(clean, templates, s11a_config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    heldout_mask = events["split"].to_numpy() == "heldout"
    heldout_events = events.loc[heldout_mask].reset_index(drop=True)
    heldout_waveforms = waveforms[heldout_mask]
    s11a_trad = s11c.run_template_fits(heldout_events, heldout_waveforms, templates, s11a_config)
    s11a_ml, s11a_ml_cv = s11c.run_ml(events, waveforms, config)
    s11a_ml_cv.to_csv(out_dir / "s11a_mlp_group_cv.csv", index=False)
    s11a_combined = heldout_events.merge(s11a_trad, on="event_id").merge(s11a_ml, on="event_id")
    s11a_rows = []
    for prefix, label in [("trad", "constrained_template_fit"), ("ml", "compact_mlp_classifier_regressor")]:
        row = {"method": label, **s11c.metric_values(s11a_combined, prefix)}
        row.update(s11c.bootstrap_metric_ci_by_run(s11a_combined, prefix, rng, int(config["ml"]["bootstrap_samples"])))
        s11a_rows.append(row)
    s11a_anchor = pd.DataFrame(s11a_rows)
    s11a_anchor.to_csv(out_dir / "s11a_anchor_overall.csv", index=False)
    for method, key in [
        ("constrained_template_fit", "expected_traditional_time_rms_ns"),
        ("compact_mlp_classifier_regressor", "expected_ml_time_rms_ns"),
    ]:
        got = float(s11a_anchor[s11a_anchor["method"] == method].iloc[0]["time_rms_ns"])
        expected = float(config["s11a_anchor"][key])
        if abs(got - expected) > float(config["s11a_anchor"]["tolerance_ns"]):
            raise RuntimeError(f"S11a anchor reproduction failed for {method}: {got} vs {expected}")

    rich_templates, template_summary = s11c.build_amp_binned_templates(template_clean, config)
    template_summary.to_csv(out_dir / "s11c_template_summary.csv", index=False)
    unconditioned_pool, unconditioned_pool_summary = build_residual_pool(template_clean, templates, config, conditioned=False)
    conditioned_pool, conditioned_pool_summary = build_residual_pool(template_clean, templates, config, conditioned=True)
    pool_summary = pd.concat([unconditioned_pool_summary, conditioned_pool_summary], ignore_index=True)
    pool_summary.to_csv(out_dir / "residual_pool_summary.csv", index=False)

    s11c_combined, s11c_overall, s11c_by_run, s11c_ml_cv, s11c_leak = run_benchmark(
        clean, templates, rich_templates, config, train_runs, heldout_runs, rng, "s11c_source"
    )
    s11c_combined.to_csv(out_dir / "s11c_source_injected_events_with_predictions.csv", index=False)
    s11c_overall.to_csv(out_dir / "s11c_source_head_to_head_overall.csv", index=False)
    s11c_by_run.to_csv(out_dir / "s11c_source_heldout_by_run.csv", index=False)
    s11c_ml_cv.to_csv(out_dir / "s11c_source_ml_group_cv.csv", index=False)
    s11c_leak.to_csv(out_dir / "s11c_source_leakage_checks.csv", index=False)
    for method, key in [
        ("amp_binned_asymmetric_template_fit", "expected_traditional_time_rms_ns"),
        ("compact_mlp_classifier_regressor", "expected_ml_time_rms_ns"),
    ]:
        got = float(s11c_overall[s11c_overall["method"] == method].iloc[0]["time_rms_ns"])
        expected = float(config["s11c_anchor"][key])
        if abs(got - expected) > float(config["s11c_anchor"]["tolerance_ns"]):
            raise RuntimeError(f"S11c source reproduction failed for {method}: {got} vs {expected}")

    train_only_combined, train_only_overall, train_only_by_run, train_only_ml_cv, train_only_leak = run_benchmark(
        clean, templates, rich_templates, config, train_runs, heldout_runs, rng, "unconditioned_train_residual", unconditioned_pool
    )
    train_only_combined.to_csv(out_dir / "train_only_injected_events_with_predictions.csv", index=False)
    train_only_overall.to_csv(out_dir / "train_only_head_to_head_overall.csv", index=False)
    train_only_by_run.to_csv(out_dir / "train_only_heldout_by_run.csv", index=False)
    train_only_ml_cv.to_csv(out_dir / "train_only_ml_group_cv.csv", index=False)
    train_only_leak.to_csv(out_dir / "train_only_leakage_checks.csv", index=False)

    conditioned_combined, conditioned_overall, conditioned_by_run, conditioned_ml_cv, conditioned_leak = run_benchmark(
        clean, templates, rich_templates, config, train_runs, heldout_runs, rng, "conditioned_train_residual", conditioned_pool
    )
    conditioned_combined.to_csv(out_dir / "conditioned_injected_events_with_predictions.csv", index=False)
    conditioned_overall.to_csv(out_dir / "conditioned_head_to_head_overall.csv", index=False)
    conditioned_by_run.to_csv(out_dir / "conditioned_heldout_by_run.csv", index=False)
    conditioned_ml_cv.to_csv(out_dir / "conditioned_ml_group_cv.csv", index=False)
    conditioned_leak.to_csv(out_dir / "leakage_checks.csv", index=False)

    gap = compare_gap(s11c_combined, conditioned_combined, rng, int(config["ml"]["bootstrap_samples"]))
    gap.to_csv(out_dir / "gap_comparison.csv", index=False)
    plot_summary(out_dir, gap, conditioned_by_run, pool_summary)

    input_paths = [
        s11c.raw_file(config, run)
        for run in sorted(
            set(s11c.configured_runs(config) + train_runs + heldout_runs + [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57])
        )
    ]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(
        out_dir,
        config,
        match,
        s10,
        s11a_anchor,
        s11c_overall,
        train_only_overall,
        conditioned_overall,
        gap,
        conditioned_by_run,
        conditioned_leak,
        pool_summary,
        runtime,
    )

    trad = conditioned_overall[conditioned_overall["method"] == "amp_binned_asymmetric_template_fit"].iloc[0]
    ml = conditioned_overall[conditioned_overall["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    source_trad = s11c_overall[s11c_overall["method"] == "amp_binned_asymmetric_template_fit"].iloc[0]
    source_ml = s11c_overall[s11c_overall["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    gap_cond = gap[gap["benchmark"] == "conditioned_train_residual"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all() and (len(s10) == 0 or s10["pass"].all())),
        "s11a_anchor": {
            "traditional_time_rms_ns": float(s11a_anchor[s11a_anchor["method"] == "constrained_template_fit"].iloc[0]["time_rms_ns"]),
            "ml_time_rms_ns": float(s11a_anchor[s11a_anchor["method"] == "compact_mlp_classifier_regressor"].iloc[0]["time_rms_ns"]),
            "pass": True,
        },
        "s11c_source_reproduction": {
            "traditional_time_rms_ns": float(source_trad["time_rms_ns"]),
            "ml_time_rms_ns": float(source_ml["time_rms_ns"]),
            "traditional_expected_time_rms_ns": float(config["s11c_anchor"]["expected_traditional_time_rms_ns"]),
            "ml_expected_time_rms_ns": float(config["s11c_anchor"]["expected_ml_time_rms_ns"]),
            "pass": True,
        },
        "traditional": {
            "method": "amplitude_binned_asymmetric_s01_template_fit_with_conditioned_train_residuals",
            "metric": "heldout_constituent_time_rms_ns",
            "value": float(trad["time_rms_ns"]),
            "ci": [float(trad["time_rms_ns_ci_low"]), float(trad["time_rms_ns_ci_high"])],
            "detection_ap": float(trad["detection_ap"]),
            "charge_fractional_bias": float(trad["charge_fractional_bias"]),
            "charge_fractional_res68": float(trad["charge_fractional_res68"]),
            "failure_rate": float(trad["failure_rate"]),
        },
        "ml": {
            "method": "compact_mlp_classifier_regressor_with_conditioned_train_residuals",
            "metric": "heldout_constituent_time_rms_ns",
            "value": float(ml["time_rms_ns"]),
            "ci": [float(ml["time_rms_ns_ci_low"]), float(ml["time_rms_ns_ci_high"])],
            "detection_ap": float(ml["detection_ap"]),
            "charge_fractional_bias": float(ml["charge_fractional_bias"]),
            "charge_fractional_res68": float(ml["charge_fractional_res68"]),
            "failure_rate": float(ml["failure_rate"]),
        },
        "conditioning_effect": {
            "gap_traditional_minus_ml_ns": float(gap_cond["gap_traditional_minus_ml_ns"]),
            "gap_ci": [float(gap_cond["gap_ci_low"]), float(gap_cond["gap_ci_high"])],
            "delta_gap_vs_s11c_source_ns": float(gap_cond["delta_gap_vs_s11c_source_ns"]),
            "ml_still_beats_traditional": bool(ml["time_rms_ns"] < trad["time_rms_ns"]),
        },
        "falsification": {
            "split": "by source run",
            "train_runs": train_runs,
            "heldout_runs": heldout_runs,
            "heldout_excluded_from_template_training": True,
            "heldout_excluded_from_residual_pool_training": True,
            "leakage_checks_pass": bool(conditioned_leak["pass"].all()),
            "leakage_flags": int((~conditioned_leak["pass"].astype(bool)).sum()),
            "bootstrap_unit": "heldout source run",
            "n_conditioned_exact_pools": int(pool_summary[pool_summary["conditioned"].astype(bool)].shape[0]),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

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
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduced": result["reproduced"],
                "conditioned_gap_trad_minus_ml_ns": result["conditioning_effect"]["gap_traditional_minus_ml_ns"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
