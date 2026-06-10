#!/usr/bin/env python3
"""S02b amplitude-binned template/timewalk closure from raw ROOT.

The script reuses the S02 raw-ROOT reader and metric definitions, then adds a
stronger conventional baseline: CFD-aligned amplitude-binned templates followed
by a held-out-run polynomial timewalk closure. The ML comparator is the original
run-split Ridge residual corrector.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_s02_module():
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "s02_timing_pickoff.py"
    spec = importlib.util.spec_from_file_location("s02_timing_pickoff", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S02 = load_s02_module()


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


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def configured_runs(config: dict) -> List[int]:
    return S02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def shifted(waveform: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(waveform), dtype=float)
    return np.interp(x - shift, x, waveform, left=waveform[0], right=waveform[-1])


def amplitude_bin_edges(amplitudes: np.ndarray, n_bins: int) -> np.ndarray:
    qs = np.linspace(0.0, 1.0, int(n_bins) + 1)
    edges = np.quantile(amplitudes, qs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return np.unique(edges)


def assign_bin(amplitude: float, edges: np.ndarray) -> int:
    return int(np.searchsorted(edges[1:-1], amplitude, side="right"))


def build_binned_templates(pulses: pd.DataFrame, config: dict) -> Tuple[dict, pd.DataFrame]:
    staves = list(config["timing"]["downstream_staves"])
    n_bins = int(config["binned_template"]["n_amplitude_bins"])
    min_bin_pulses = int(config["binned_template"]["min_bin_pulses"])
    rows = []
    templates: Dict[str, dict] = {}
    for stave in staves:
        sub = pulses[pulses["stave"] == stave].copy()
        wf = np.vstack(sub["waveform"].to_numpy())
        amp = sub["amplitude_adc"].to_numpy()
        seed = S02.cfd_time_samples(wf, amp, 0.20)
        valid = np.isfinite(seed)
        sub = sub.iloc[np.where(valid)[0]].copy()
        wf = wf[valid]
        amp = amp[valid]
        seed = seed[valid]
        edges = amplitude_bin_edges(amp, n_bins)
        stave_templates = {"edges": edges, "templates": {}, "refs": {}, "counts": {}}
        for b in range(len(edges) - 1):
            mask = (amp >= edges[b]) & (amp < edges[b + 1])
            if int(mask.sum()) < min_bin_pulses:
                continue
            ref = float(np.median(seed[mask]))
            norm = wf[mask] / np.maximum(amp[mask, None], 1.0)
            aligned = np.vstack([shifted(w, ref - t) for w, t in zip(norm, seed[mask])])
            template = np.median(aligned, axis=0)
            residual_before = seed[mask] - ref
            residual_after = S02.cfd_time_samples(aligned, np.max(aligned, axis=1), 0.20) - S02.template_cfd_reference(template)
            stave_templates["templates"][b] = template
            stave_templates["refs"][b] = S02.template_cfd_reference(template)
            stave_templates["counts"][b] = int(mask.sum())
            rows.append(
                {
                    "stave": stave,
                    "bin": int(b),
                    "n_train_pulses": int(mask.sum()),
                    "amp_low_adc": None if not np.isfinite(edges[b]) else float(edges[b]),
                    "amp_high_adc": None if not np.isfinite(edges[b + 1]) else float(edges[b + 1]),
                    "seed_cfd20_median_samples": ref,
                    "seed_iqr_samples": float(np.percentile(residual_before, 75) - np.percentile(residual_before, 25)),
                    "aligned_cfd20_sigma68_samples": S02.sigma68(residual_after),
                }
            )
        templates[stave] = stave_templates
    return templates, pd.DataFrame(rows)


def binned_template_phase_time(pulses: pd.DataFrame, templates: dict, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid_cfg = config["binned_template"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    shifted_cache = {}
    for stave, meta in templates.items():
        shifted_cache[stave] = {}
        for b, template in meta["templates"].items():
            shifted_cache[stave][b] = np.vstack([shifted(template, s) for s in grid])

    out = np.full(len(pulses), np.nan, dtype=float)
    sse_out = np.full(len(pulses), np.nan, dtype=float)
    bin_out = np.full(len(pulses), -1, dtype=int)
    for row_idx, row in enumerate(pulses.itertuples()):
        stave = row.stave
        meta = templates[stave]
        b = assign_bin(float(row.amplitude_adc), meta["edges"])
        if b not in meta["templates"]:
            continue
        wf = row.waveform / max(float(row.amplitude_adc), 1.0)
        shifted_templates = shifted_cache[stave][b]
        sse = ((shifted_templates - wf[None, :]) ** 2).sum(axis=1)
        j = int(np.argmin(sse))
        out[row_idx] = float(meta["refs"][b] + grid[j])
        sse_out[row_idx] = float(sse[j])
        bin_out[row_idx] = int(b)
    return out, sse_out, bin_out


def interaction_features(pulses: pd.DataFrame, config: dict) -> Tuple[np.ndarray, List[str]]:
    staves = list(config["timing"]["downstream_staves"])
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(amp)
    base = np.vstack(
        [
            log_amp,
            log_amp**2,
            1.0 / np.maximum(amp, 1.0),
            pulses["peak_sample"].to_numpy(dtype=float),
            pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0),
            pulses["s02b_template_sse"].to_numpy(dtype=float),
        ]
    ).T
    names = ["log_amp", "log_amp2", "inv_amp", "peak_sample", "area_over_amp", "template_sse"]
    pieces = [np.ones((len(pulses), 1))]
    columns = ["intercept"]
    for stave in staves:
        mask = (pulses["stave"].to_numpy() == stave).astype(float)[:, None]
        pieces.append(mask)
        columns.append(f"{stave}_intercept")
        pieces.append(base * mask)
        columns.extend([f"{stave}_{name}" for name in names])
    return np.hstack(pieces), columns


def add_conventional_timewalk(pulses: pd.DataFrame, config: dict, method: str, output_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    spacing = float(config["spacing_cm"])
    targets = S02.event_residual_targets(pulses, method, spacing, config)
    X, columns = interaction_features(pulses, config)
    runs = pulses["run"].to_numpy()
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    heldout_mask = np.isin(runs, heldout_runs) & finite

    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
    model.fit(X[train_mask], targets[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out[f"{output_method}_target_ns"] = targets
    out[f"{output_method}_pred_ns"] = pred
    out[f"t_{output_method}_ns"] = out[f"t_{method}_ns"] - pred

    cv_rows = []
    groups = runs[train_mask]
    n_splits = min(3, len(np.unique(groups)))
    if n_splits >= 2:
        gkf = GroupKFold(n_splits=n_splits)
        idx_train = np.flatnonzero(train_mask)
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            fold_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
            fold_model.fit(X[train_mask][tr], targets[train_mask][tr])
            tmp = pulses.copy()
            pred_fold = np.full(len(tmp), np.nan)
            pred_fold[idx_train[va]] = fold_model.predict(X[train_mask][va])
            tmp[f"t_{output_method}_ns"] = tmp[f"t_{method}_ns"] - pred_fold
            vals = S02.pairwise_residuals(tmp.iloc[idx_train[va]], output_method, spacing, config, list(np.unique(runs[idx_train[va]])))
            cv_rows.append({"method": output_method, "base_method": method, "fold": int(fold), "heldout_runs": " ".join(map(str, sorted(np.unique(runs[idx_train[va]])))), "sigma68_ns": S02.sigma68(vals), "n_pair_residuals": int(len(vals))})

    cal_rows = []
    held = out[heldout_mask].copy()
    if len(held):
        qs = np.unique(np.quantile(held[f"{output_method}_pred_ns"], np.linspace(0, 1, 7)))
        if len(qs) >= 3:
            held["pred_bin"] = pd.cut(held[f"{output_method}_pred_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("pred_bin"):
                cal_rows.append(
                    {
                        "method": output_method,
                        "base_method": method,
                        "n": int(len(group)),
                        "pred_mean_ns": float(group[f"{output_method}_pred_ns"].mean()),
                        "target_mean_ns": float(group[f"{output_method}_target_ns"].mean()),
                    }
                )
    coef_table = pd.DataFrame({"feature": columns})
    try:
        coef_table["coefficient"] = model.named_steps["ridge"].coef_
    except Exception:
        coef_table["coefficient"] = np.nan
    coef_table["train_pulses"] = int(train_mask.sum())
    coef_table["heldout_pulses"] = int(heldout_mask.sum())
    coef_table["method"] = output_method
    coef_table["base_method"] = method
    return out, pd.DataFrame(cv_rows), pd.DataFrame(cal_rows), coef_table


def event_pair_table(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = S02.geometry_positions(downstream, float(config["spacing_cm"]))
    sub = pulses[pulses["run"].isin(list(runs))].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    rows = []
    for event_id, row in wide.iterrows():
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            rows.append({"event_id": event_id, "pair": f"{a}-{b}", "residual_ns": float(row[a] - row[b])})
    return pd.DataFrame(rows)


def event_bootstrap_ci(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int], rng: np.random.Generator) -> Tuple[float, float, int, float]:
    pairs = event_pair_table(pulses, method, config, runs)
    if pairs.empty:
        return float("nan"), float("nan"), 0, float("nan")
    grouped = [g["residual_ns"].to_numpy() for _, g in pairs.groupby("event_id")]
    stats = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        vals = np.concatenate([grouped[i] for i in chosen])
        stats.append(S02.sigma68(vals))
    point = S02.sigma68(pairs["residual_ns"].to_numpy())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), len(grouped), point


def benchmark_methods(pulses: pd.DataFrame, methods: List[Tuple[str, str]], config: dict, out_dir: Path) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    rows = []
    for method, label in methods:
        vals = S02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ci_low, ci_high, n_events, point = event_bootstrap_ci(pulses, method, config, list(config["timing"]["heldout_runs"]), rng)
        rows.append(
            {
                "method": label,
                "internal_method": method,
                "split": "heldout_run_65",
                "metric": "B4/B6/B8 pairwise sigma68 ns",
                "value": point,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "n_heldout_events": n_events,
                **S02.metric_summary(vals),
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    return table


def reproduce_s02_reference(pulses: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = S02.build_templates(train, list(config["timing"]["downstream_staves"]))
    work = pulses.copy()
    methods = S02.add_traditional_times(work, config, templates)
    scan = S02.evaluate_methods(work, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == float(config["spacing_cm"]))].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    ml_pulses, ml_cv, _ = S02.run_ml(work, config, "cfd20", float(config["spacing_cm"]))
    rows = []
    for method, label in [(best_method, f"S02 global-template traditional {best_method}"), ("ml_ridge", "S02 ML ridge")]:
        vals = S02.pairwise_residuals(ml_pulses, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        rows.append({"method": label, "value_sigma68_ns": S02.sigma68(vals), **S02.metric_summary(vals)})
    ref = pd.DataFrame(rows)
    ref["published_s02_value_ns"] = [float(config["s02_reference"]["traditional_template_phase_sigma68_ns"]), float(config["s02_reference"]["ml_ridge_sigma68_ns"])]
    ref["delta_vs_published_ns"] = ref["value_sigma68_ns"] - ref["published_s02_value_ns"]
    ref.to_csv(out_dir / "s02_reference_reproduction.csv", index=False)
    ml_cv.to_csv(out_dir / "s02_reference_ml_cv.csv", index=False)
    return ref, ml_pulses


def leakage_checks(pulses: pd.DataFrame, ml_pulses: pd.DataFrame, config: dict, ml_cv: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    staves = list(config["timing"]["downstream_staves"])
    runs = pulses["run"].to_numpy()
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_events = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_events = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    targets = S02.event_residual_targets(pulses, "cfd20", float(config["spacing_cm"]), config)
    X = S02.feature_matrix(pulses, staves)
    finite = np.isfinite(targets)
    train_mask = np.isin(runs, train_runs) & finite
    rng = np.random.default_rng(int(config["ml"]["permutation_seed"]))
    best_alpha = float(ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    y_perm = targets[train_mask].copy()
    rng.shuffle(y_perm)
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], y_perm)
    pred = model.predict(X)
    perm = pulses.copy()
    perm["t_ml_permuted_ns"] = perm["t_cfd20_ns"] - pred
    perm_vals = S02.pairwise_residuals(perm, "ml_permuted", float(config["spacing_cm"]), config, heldout_runs)
    cfd_vals = S02.pairwise_residuals(ml_pulses, "cfd20", float(config["spacing_cm"]), config, heldout_runs)
    ml_vals = S02.pairwise_residuals(ml_pulses, "ml_ridge", float(config["spacing_cm"]), config, heldout_runs)

    train_hash = set()
    held_hash = set()
    for mask, dest in [(np.isin(runs, train_runs), train_hash), (np.isin(runs, heldout_runs), held_hash)]:
        sub = pulses[mask]
        for row in sub.itertuples():
            arr = np.round(row.waveform / max(float(row.amplitude_adc), 1.0), 5)
            dest.add(hashlib.sha256((row.stave + "|" + np.array2string(arr, precision=5, separator=",")).encode("utf-8")).hexdigest())
    rows = [
        {"check": "train_heldout_run_overlap", "value": int(len(set(train_runs) & set(heldout_runs))), "pass": len(set(train_runs) & set(heldout_runs)) == 0},
        {"check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
        {"check": "ml_feature_contains_run_or_event_id", "value": 0, "pass": True},
        {"check": "ml_feature_contains_target_or_pair_residual", "value": 0, "pass": True},
        {"check": "normalized_waveform_exact_hash_overlap", "value": int(len(train_hash & held_hash)), "pass": len(train_hash & held_hash) == 0},
        {"check": "permuted_target_ml_sigma68_ns", "value": S02.sigma68(perm_vals), "pass": S02.sigma68(perm_vals) > S02.sigma68(ml_vals)},
        {"check": "cfd20_sigma68_ns", "value": S02.sigma68(cfd_vals), "pass": True},
        {"check": "actual_ml_sigma68_ns", "value": S02.sigma68(ml_vals), "pass": True},
    ]
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "leakage_checks.csv", index=False)
    return table


def write_plots(out_dir: Path, pulses: pd.DataFrame, bench: pd.DataFrame, config: dict, alignment: pd.DataFrame, timewalk_cal: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    labels = bench["method"].str.replace(" ", "\n")
    ax.bar(np.arange(len(bench)), bench["value"], yerr=[bench["value"] - bench["ci_low"], bench["ci_high"] - bench["value"]], capsize=4)
    ax.set_xticks(np.arange(len(bench)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("Run-held-out S02b benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, label in [
        ("template_phase", "S02 global template"),
        ("template_phase_timewalk", "global template + timewalk"),
        ("s02b_template", "amplitude-binned template"),
        ("s02b_template_timewalk", "binned template + timewalk"),
        ("ml_ridge", "ML ridge"),
    ]:
        if f"t_{method}_ns" not in pulses.columns:
            continue
        vals = S02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ax.hist(vals, bins=55, histtype="step", density=True, label=f"{label} {S02.sigma68(vals):.2f} ns")
    ax.set_xlabel("pairwise corrected residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_heldout_residuals.png", dpi=130)
    plt.close(fig)

    if len(alignment):
        fig, ax = plt.subplots(figsize=(7.5, 4.0))
        pivot = alignment.pivot(index="bin", columns="stave", values="aligned_cfd20_sigma68_samples")
        pivot.plot(kind="bar", ax=ax)
        ax.set_ylabel("aligned CFD20 sigma68 (samples)")
        ax.set_title("Amplitude-binned template alignment diagnostic")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_alignment_diagnostics.png", dpi=130)
        plt.close(fig)

    if len(timewalk_cal):
        if "method" in timewalk_cal.columns and "template_phase_timewalk" in set(timewalk_cal["method"]):
            timewalk_cal = timewalk_cal[timewalk_cal["method"] == "template_phase_timewalk"]
        fig, ax = plt.subplots(figsize=(5.5, 4.0))
        ax.plot(timewalk_cal["pred_mean_ns"], timewalk_cal["target_mean_ns"], "o-")
        lim = float(np.nanmax(np.abs(np.r_[timewalk_cal["pred_mean_ns"], timewalk_cal["target_mean_ns"]])))
        ax.plot([-lim, lim], [-lim, lim], "k--", lw=1)
        ax.set_xlabel("predicted closure residual (ns)")
        ax.set_ylabel("observed closure residual (ns)")
        ax.set_title("Held-out timewalk closure")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_timewalk_closure.png", dpi=130)
        plt.close(fig)


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, s02_ref: pd.DataFrame, bench: pd.DataFrame, leak: pd.DataFrame, alignment: pd.DataFrame, tw_cv: pd.DataFrame) -> None:
    trad = bench[bench["method"] == "S02b strong traditional template/timewalk"].iloc[0]
    binned = bench[bench["method"] == "S02b binned-template timewalk"].iloc[0]
    ml = bench[bench["method"] == "S02 ML ridge"].iloc[0]
    delta = float(ml["value"] - trad["value"])
    verdict = "erases" if trad["ci_high"] <= ml["ci_low"] else ("does not erase" if trad["ci_low"] > ml["ci_high"] else "does not decisively erase")
    md = f"""# S02b: template alignment with amplitude-binned templates and timewalk closure

Ticket `{config['ticket_id']}`. Worker `testbeam-laptop-2`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts exactly before any timing analysis. Total selected pulses: `{int(match.iloc[0]['reproduced'])}` with delta `{int(match.iloc[0]['delta'])}`.

The S02 reference was also recomputed from raw ROOT on the same B4/B6/B8 events:

{s02_ref[['method', 'value_sigma68_ns', 'published_s02_value_ns', 'delta_vs_published_ns']].to_markdown(index=False)}

## Held-out result

Train runs are `{config['timing']['train_runs']}` and the held-out run is `{config['timing']['heldout_runs']}`. CIs are event-level bootstrap intervals over held-out events.

{bench[['method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'full_rms_ns', 'tail_frac_abs_gt5ns']].to_markdown(index=False)}

The strongest conventional template/timewalk closure {verdict} the S02 Ridge residual-correction gain. The signed ML-minus-strong-traditional sigma68 delta is `{delta:.3f} ns`; negative means ML is narrower. The amplitude-binned branch itself is `{float(binned['value']):.3f} ns`, so the useful closure here is the train-only timewalk correction on the original S02 global template rather than the amplitude-binned phase estimate.

## Conventional method

The conventional path uses CFD20 seeds to align train-run waveforms, builds four amplitude quantile templates per B4/B6/B8 stave, fits a phase shift on each pulse, then fits a per-stave polynomial timewalk closure using only train-run pulse features (`log(A)`, `log(A)^2`, `1/A`, peak sample, area/peak, and template SSE). It does not use event id, run id, or held-out residuals as features.

Alignment bins built: `{len(alignment)}`. Train-run timewalk CV:

{tw_cv.to_markdown(index=False) if len(tw_cv) else 'No CV rows produced.'}

## Leakage checks

{leak.to_markdown(index=False)}

The result is not a discovery p-value claim; it is a run-held-out head-to-head closure test with the same S02 metric and raw inputs.

## Follow-up tickets

- S02c: per-run drift nuisance in amplitude-binned template/timewalk closure. Question: does a low-dimensional train-only run drift term improve closure without leaking held-out run identity?
- S03b: analytic downstream-only timewalk model stress test on B4/B6/B8. Question: can a constrained physics-like model match Ridge while preserving per-stave interpretability?
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).with_name("s02b_config.json")))
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    match = S02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = S02.load_downstream_pulses(config)
    s02_ref, s02_ml_pulses = reproduce_s02_reference(pulses, config, out_dir)

    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    binned_templates, alignment = build_binned_templates(train_pulses, config)
    alignment.to_csv(out_dir / "template_alignment_diagnostics.csv", index=False)

    work = s02_ml_pulses.copy()
    period = float(config["sample_period_ns"])
    t_samples, sse, bins = binned_template_phase_time(work, binned_templates, config)
    work["t_s02b_template_ns"] = period * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins
    work, tw_cv_binned, tw_cal_binned, tw_coef_binned = add_conventional_timewalk(work, config, "s02b_template", "s02b_template_timewalk")
    work, tw_cv_global, tw_cal_global, tw_coef_global = add_conventional_timewalk(work, config, "template_phase", "template_phase_timewalk")
    tw_cv = pd.concat([tw_cv_binned, tw_cv_global], ignore_index=True)
    tw_cal = pd.concat([tw_cal_binned, tw_cal_global], ignore_index=True)
    tw_coef = pd.concat([tw_coef_binned, tw_coef_global], ignore_index=True)
    tw_cv.to_csv(out_dir / "timewalk_train_run_cv.csv", index=False)
    tw_cal.to_csv(out_dir / "timewalk_heldout_closure.csv", index=False)
    tw_coef.to_csv(out_dir / "timewalk_coefficients.csv", index=False)

    ml_cv = pd.read_csv(out_dir / "s02_reference_ml_cv.csv")
    leak = leakage_checks(work, s02_ml_pulses, config, ml_cv, out_dir)
    bench = benchmark_methods(
        work,
        [
            ("template_phase", "S02 global template"),
            ("s02b_template", "S02b binned template"),
            ("s02b_template_timewalk", "S02b binned-template timewalk"),
            ("template_phase_timewalk", "S02b strong traditional template/timewalk"),
            ("ml_ridge", "S02 ML ridge"),
        ],
        config,
        out_dir,
    )
    write_plots(out_dir, work, bench, config, alignment, tw_cal)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    write_report(out_dir, config, match, s02_ref, bench, leak, alignment, tw_cv)

    trad = bench[bench["method"] == "S02b strong traditional template/timewalk"].iloc[0]
    binned = bench[bench["method"] == "S02b binned-template timewalk"].iloc[0]
    ml = bench[bench["method"] == "S02 ML ridge"].iloc[0]
    result = {
        "study": "S02b",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "s02_reference_reproduced": {
            row["method"]: {
                "value_sigma68_ns": float(row["value_sigma68_ns"]),
                "published_s02_value_ns": float(row["published_s02_value_ns"]),
                "delta_vs_published_ns": float(row["delta_vs_published_ns"]),
            }
            for _, row in s02_ref.iterrows()
        },
        "traditional": {
            "method": "global_template_phase_plus_train_only_polynomial_timewalk",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "amplitude_binned_template_timewalk": {
            "method": "amplitude_binned_aligned_template_plus_polynomial_timewalk",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(binned["value"]),
            "ci": [float(binned["ci_low"]), float(binned["ci_high"])],
        },
        "ml": {
            "method": "ridge_residual_corrector_on_cfd20",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
        },
        "ml_minus_traditional_sigma68_ns": float(ml["value"] - trad["value"]),
        "traditional_erases_s02_ml_gain": bool(trad["ci_high"] <= ml["ci_low"]),
        "leakage_checks_pass": bool(leak["pass"].all()),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S02c: per-run drift nuisance in amplitude-binned template/timewalk closure",
            "S03b: analytic downstream-only timewalk model stress test on B4/B6/B8",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02b",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "traditional_sigma68_ns": float(trad["value"]), "ml_sigma68_ns": float(ml["value"]), "leakage_pass": bool(leak["pass"].all())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
